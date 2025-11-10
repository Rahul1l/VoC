import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    MONGODB_URI = os.getenv('MONGODB_URI')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
    
    # Admin credentials
    ADMIN_USERNAME = 'Ayushman'
    ADMIN_PASSWORD = 'ayushman9277'
    
    # Trainer list
    TRAINERS = [
        'Nitesh Dhar Badgayan',
        'Amit Chaudhary',
        'Lijin',
        'Ayushman Ghosh',
        'Mohan Reddy',
        'Snehasish Guha',
        'Rajeev Anwar',
        'Shalini Kanagasabapathy',
        'Jagadish GS',
        'Omkar Jagtap',
        'Siddharth'
    ]

