from flask_login import UserMixin
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from bson.objectid import ObjectId

load_dotenv(override=True)
uri = os.getenv("MONGO_URI")

client = MongoClient(uri)
db = client[os.getenv("MONGO_DBNAME")]

class User(UserMixin):
    def __init__(self, user_dict):
        self.username = user_dict['username']
        self.id = str(user_dict['_id']) 

    @staticmethod
    def get(user_id):
        user_data = db.users.find_one({"_id": ObjectId(user_id)})
        if user_data:
            return User(user_data)
        return None
    
    @staticmethod
    def create(username,password):
        result = db.users.insert_one({'username': username, 'password': password})
        return User({'username': username, '_id': result.inserted_id})
    
    @staticmethod
    def validate_login(username, password):
        user = db.users.find_one({"username": username})
        if user and user['password'] == password:
            return User(user)
        return None
    
    @staticmethod
    def get_by_username(username):
        user = db.users.find_one({"username": username})
        if user:
            return User(user)
        return None