from app import scheduler_db

class Availability(scheduler_db.Model):
    id = scheduler_db.Column(scheduler_db.Integer, primary_key=True)
    group_id = scheduler_db.Column(scheduler_db.Integer, scheduler_db.ForeignKey('group.id'), nullable=False)
    weekday = scheduler_db.Column(scheduler_db.Integer, nullable=False)
    hour = scheduler_db.Column(scheduler_db.Float, nullable=False)
    
    def __repr__(self):
        return f"<Availability group_id={self.group_id} weekday={self.weekday} hour={self.hour}>"