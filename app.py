from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from pymongo import MongoClient
from bson import ObjectId
from transformers import pipeline
from openai import OpenAI
import os
from config import Config
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

# MongoDB connection
client = MongoClient(Config.MONGODB_URI)
db = client['voc_db']
universities_collection = db['universities']
feedback_collection = db['feedback']

# Initialize RoBERTa sentiment analyzer
try:
    sentiment_analyzer = pipeline("sentiment-analysis", model="cardiffnlp/twitter-roberta-base-sentiment-latest")
except Exception as e:
    print(f"Error loading RoBERTa model: {e}")
    sentiment_analyzer = None

# Initialize OpenAI
openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)

def analyze_sentiment_roberta(text):
    """Analyze sentiment using RoBERTa model and return score 0-5"""
    if not sentiment_analyzer or not text:
        return 3.0
    
    try:
        result = sentiment_analyzer(text)[0]
        label = result['label']
        score = result['score']
        
        # Map sentiment to 0-5 scale
        # LABEL_0: negative, LABEL_1: neutral, LABEL_2: positive
        if 'LABEL_0' in label or 'NEGATIVE' in label.upper():
            # Negative: 0-2.5
            return round(score * 2.5, 2)
        elif 'LABEL_1' in label or 'NEUTRAL' in label.upper():
            # Neutral: 2.5-3.5
            return round(2.5 + (score * 1.0), 2)
        else:
            # Positive: 3.5-5
            return round(3.5 + (score * 1.5), 2)
    except Exception as e:
        print(f"Error in sentiment analysis: {e}")
        return 3.0

def get_improvement_suggestions(feedback_text, kpi_scores):
    """Generate improvement suggestions using OpenAI"""
    try:
        prompt = f"""Based on the following feedback and KPI scores, provide specific, actionable improvement suggestions:

Feedback: {feedback_text}
KPI Scores: {json.dumps(kpi_scores)}

Provide 3-5 concise improvement suggestions focusing on areas that scored below 4.0. Format as a bulleted list."""
        
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a feedback analysis expert providing actionable improvement suggestions."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating suggestions: {e}")
        return "Unable to generate suggestions at this time."

@app.route('/')
def index():
    if 'admin_logged_in' in session:
        return redirect(url_for('admin_page'))
    if 'user_logged_in' in session:
        return redirect(url_for('feedback_page'))
    return render_template('index.html', page='login')

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    # Check admin credentials
    if username == Config.ADMIN_USERNAME and password == Config.ADMIN_PASSWORD:
        session['admin_logged_in'] = True
        session['username'] = username
        return jsonify({'success': True, 'role': 'admin'})
    
    # Check user credentials
    user = universities_collection.find_one({
        'username': username,
        'password': password
    })
    
    if user:
        session['user_logged_in'] = True
        session['username'] = username
        session['university_name'] = user.get('university_name', '')
        return jsonify({'success': True, 'role': 'user'})
    
    return jsonify({'success': False, 'message': 'Invalid credentials'})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/admin')
def admin_page():
    if 'admin_logged_in' not in session:
        return redirect(url_for('index'))
    return render_template('index.html', page='admin')

@app.route('/feedback')
def feedback_page():
    if 'user_logged_in' not in session:
        return redirect(url_for('index'))
    return render_template('index.html', page='feedback')

@app.route('/api/universities', methods=['POST'])
def create_university():
    if 'admin_logged_in' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.json
    university_name = data.get('university_name', '').strip()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if not university_name or not username or not password:
        return jsonify({'success': False, 'message': 'All fields are required'})
    
    # Check if username already exists
    existing = universities_collection.find_one({'username': username})
    if existing:
        return jsonify({'success': False, 'message': 'Username already exists'})
    
    universities_collection.insert_one({
        'university_name': university_name,
        'username': username,
        'password': password,
        'created_at': datetime.now()
    })
    
    return jsonify({'success': True, 'message': 'University added successfully'})

@app.route('/api/universities', methods=['GET'])
def get_universities():
    if 'admin_logged_in' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    universities = list(universities_collection.find({}, {'password': 0}))
    for uni in universities:
        uni['_id'] = str(uni['_id'])
    
    return jsonify({'success': True, 'data': universities})

@app.route('/api/universities/<university_id>', methods=['GET'])
def get_university(university_id):
    if 'admin_logged_in' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    university = universities_collection.find_one({'_id': ObjectId(university_id)})
    if not university:
        return jsonify({'success': False, 'message': 'University not found'}), 404
    
    university['_id'] = str(university['_id'])
    return jsonify({'success': True, 'data': university})

@app.route('/api/universities/<university_id>', methods=['PUT'])
def update_university(university_id):
    if 'admin_logged_in' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.json
    university_name = data.get('university_name', '').strip()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if not university_name or not username or not password:
        return jsonify({'success': False, 'message': 'All fields are required'})
    
    universities_collection.update_one(
        {'_id': ObjectId(university_id)},
        {'$set': {
            'university_name': university_name,
            'username': username,
            'password': password,
            'updated_at': datetime.now()
        }}
    )
    
    return jsonify({'success': True, 'message': 'University updated successfully'})

@app.route('/api/universities/<university_id>', methods=['DELETE'])
def delete_university(university_id):
    if 'admin_logged_in' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    universities_collection.delete_one({'_id': ObjectId(university_id)})
    
    return jsonify({'success': True, 'message': 'University deleted successfully'})

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    if 'user_logged_in' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.json
    course_name = data.get('course_name', '').strip()
    trainer_name = data.get('trainer_name', '').strip()
    answer1 = data.get('answer1', '').strip()
    answer2 = data.get('answer2', '').strip()
    answer3 = data.get('answer3', '').strip()
    answer4 = data.get('answer4', '').strip()
    
    # Validation
    if not course_name or not trainer_name or not answer1 or not answer2 or not answer3:
        return jsonify({'success': False, 'message': 'Course name, trainer, and answers 1-3 are required'})
    
    # Calculate KPI scores using RoBERTa
    kpi1 = analyze_sentiment_roberta(answer1)
    kpi2 = analyze_sentiment_roberta(answer2)
    kpi3 = analyze_sentiment_roberta(answer3)
    final_kpi = round((kpi1 + kpi2 + kpi3) / 3, 2)
    
    # Generate improvement suggestions
    all_feedback = f"Q1: {answer1}\nQ2: {answer2}\nQ3: {answer3}\nQ4: {answer4}"
    kpi_scores = {
        'Learning Outcome and Skill Development': kpi1,
        'Instructor Industry Alignment': kpi2,
        'Industry Application Readiness': kpi3,
        'Final KPI': final_kpi
    }
    improvement_suggestions = get_improvement_suggestions(all_feedback, kpi_scores)
    
    # Save to database
    feedback_collection.insert_one({
        'university_name': session.get('university_name', ''),
        'username': session.get('username', ''),
        'course_name': course_name,
        'trainer_name': trainer_name,
        'answer1': answer1,
        'answer2': answer2,
        'answer3': answer3,
        'answer4': answer4,
        'kpi_scores': kpi_scores,
        'improvement_suggestions': improvement_suggestions,
        'submitted_at': datetime.now()
    })
    
    return jsonify({'success': True, 'message': 'Feedback submitted successfully'})

@app.route('/api/feedback', methods=['GET'])
def get_feedback():
    if 'admin_logged_in' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    feedback_list = list(feedback_collection.find({}))
    for fb in feedback_list:
        fb['_id'] = str(fb['_id'])
        if 'submitted_at' in fb:
            fb['submitted_at'] = fb['submitted_at'].isoformat()
    
    return jsonify({'success': True, 'data': feedback_list})

@app.route('/api/feedback/<feedback_id>', methods=['GET'])
def get_feedback_detail(feedback_id):
    if 'admin_logged_in' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    feedback = feedback_collection.find_one({'_id': ObjectId(feedback_id)})
    if not feedback:
        return jsonify({'success': False, 'message': 'Feedback not found'}), 404
    
    feedback['_id'] = str(feedback['_id'])
    if 'submitted_at' in feedback:
        feedback['submitted_at'] = feedback['submitted_at'].isoformat()
    
    return jsonify({'success': True, 'data': feedback})

@app.route('/api/trainers', methods=['GET'])
def get_trainers():
    return jsonify({'success': True, 'data': Config.TRAINERS})

if __name__ == '__main__':
    # Server configured to listen on port 5000
    # Access via: http://98.93.36.219:5000
    app.run(host='0.0.0.0', port=5000, debug=True)

