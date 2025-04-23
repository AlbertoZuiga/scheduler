from app import scheduler_db

class Group(scheduler_db.Model):
    id = scheduler_db.Column(scheduler_db.Integer, primary_key=True)
    name = scheduler_db.Column(scheduler_db.String(150), nullable=False)
    join_token = scheduler_db.Column(scheduler_db.String(64), unique=True, nullable=False)
    owner_id = scheduler_db.Column(scheduler_db.Integer, scheduler_db.ForeignKey('user.id'), nullable=False)
    owner = scheduler_db.relationship('User', backref='groups')
    
    def __repr__(self):
        return f'<Group id={self.id} name={self.name} owner={self.owner.name} member_count={len(self.members)}>'