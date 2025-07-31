from pymongo.mongo_client import MongoClient
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Literal

Gender = Literal["male", "female"]

class Rabbit:
    uri = "mongodb://localhost:27017/"

    def __init__(self, id):
        self.mongo_client = MongoClient(self.uri)
        self.db = self.mongo_client["rabbit_manager"]
        self.rabbits_data = self.db.rabbits

        self.name = ""
        self.id = id
        self.gender: Gender = "male"
        self.is_empty = True
        self.last_breeding_date: Optional[datetime] = None
        self.father = None

        self.get_rabbit(id)

    def get_rabbit(self, id):
        rabbit_data = self.rabbits_data.find_one({"id": id})
        
        if rabbit_data:
            self.name = rabbit_data.get("name", "")
            self.id = rabbit_data["id"]
            self.gender = rabbit_data.get("gender", "male")
            self.is_empty = rabbit_data.get("is_empty", True)
            self.last_breeding_date = rabbit_data.get("last_breeding_date")
            
            father_id = rabbit_data.get("father")
            if father_id:
                self.father = Rabbit(father_id)
            else:
                self.father = None
        else:
            self.name = ""
            self.id = id
            self.gender = "male"
            self.is_empty = True
            self.last_breeding_date = None
            self.father = None

    def update_rabbit(self, name: str, id: int, gender: Gender, is_empty: bool, date: datetime, 
                    last_breeding_date: Optional[datetime], father: Optional['Rabbit']) -> 'Rabbit':
        update_data = {
            "name": name,
            "id": id,
            "gender": gender,
            "is_empty": is_empty,
            "last_breeding_date": last_breeding_date,
            "father": father.id if father else None
        }
        
        self.rabbits_data.update_one(
            {"id": id},
            {"$set": update_data},
            upsert=True
        )
        
        self.name = name
        self.id = id
        self.gender = gender
        self.is_empty = is_empty
        self.last_breeding_date = last_breeding_date
        self.father = father
        
        return self

    def save_rabbit(self):
        update_data = {
            "name": self.name,
            "id": self.id,
            "gender": self.gender,
            "is_empty": self.is_empty,
            "last_breeding_date": self.last_breeding_date,
            "father": self.father.id if self.father else None
        }
        
        self.rabbits_data.update_one(
            {"id": self.id},
            {"$set": update_data},
            upsert=True
        )

    def check_rabbit(self) -> bool:
        if self.last_breeding_date is None:
            return True
            
        time_since_last_breeding = datetime.now() - self.last_breeding_date
        return time_since_last_breeding >= timedelta(days=30)

    def get_message(self) -> str:
        gender_emoji = "♂️" if self.gender == "male" else "♀️"
        gender_text = "самец" if self.gender == "male" else "самка"
        
        father_info = f", отец: {self.father.name} (ID: {self.father.id})" if self.father else ""
        
        last_breeding_info = ""
        if self.last_breeding_date and self.gender == "female":
            days_since_breeding = (datetime.now() - self.last_breeding_date).days
            ready_for_breeding = "готов" if self.check_rabbit() else f"не готова (осталось {30 - days_since_breeding} дней)"
            last_breeding_info = f"\nПоследняя случка: {self.last_breeding_date.strftime('%Y-%m-%d')} ({ready_for_breeding})"

        if not self.is_empty:
            message = (
                f"🐰 Информация о кролике {gender_emoji}:\n"
                f"Имя: {self.name}\n"
                f"Пол: {gender_text}\n"
                f"Клетка: {self.id}\n"
                f"{last_breeding_info}"
                f"{father_info}"
            )
        else:
            message = "Клетка пуста!"
        
        return message

    def breed_rabbits(self, partner: 'Rabbit') -> bool:
        if self.gender == partner.gender:
            return False
        
        female = self if self.gender == "female" else partner
        if not female.check_rabbit():
            return False
        
        female.last_breeding_date = datetime.now()
        female.save_rabbit()
        
        return True
    
    def reset_breeding(self):
        if self.gender == "female":
            self.last_breeding_date = None
            self.save_rabbit()
            return True
        return False
    
    def get_pregnancy_status(self) -> Optional[str]:
        if self.gender != "female" or not self.last_breeding_date:
            return None
            
        days_passed = (datetime.now() - self.last_breeding_date).days
        if 28 <= days_passed <= 32:
            return "okrol"
        elif 25 <= days_passed < 28:
            return "preparing"
        return None

    @classmethod
    def get_pregnant_females(cls):
        client = MongoClient(cls.uri)
        db = client["rabbit_manager"]
        
        females = list(db.rabbits.find({
            "gender": "female",
            "is_empty": False,
            "last_breeding_date": {"$ne": None}
        }))
        
        client.close()
        return [Rabbit(f["id"]) for f in females]
    
    @classmethod
    def register_chat(cls, chat_id: int, chat_name: str):
        client = MongoClient(cls.uri)
        db = client["rabbit_manager"]
        chats = db.bot_chats
        
        chats.update_one(
            {"chat_id": chat_id},
            {"$set": {
                "chat_id": chat_id,
                "chat_name": chat_name,
                "last_active": datetime.now()
            }},
            upsert=True
        )
        client.close()

    @classmethod
    def get_active_chats(cls):
        client = MongoClient(cls.uri)
        db = client["rabbit_manager"]
        chats = list(db.bot_chats.find({}))
        client.close()
        return [{"chat_id": c["chat_id"], "name": c.get("chat_name", "Без названия")} for c in chats]