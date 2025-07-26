from flask_login import UserMixin

from app.extensions import scheduler_db


class User(UserMixin, scheduler_db.Model):
    id = scheduler_db.Column(scheduler_db.Integer, primary_key=True)
    email = scheduler_db.Column(scheduler_db.String(150), unique=True, nullable=False)
    name = scheduler_db.Column(scheduler_db.String(150), nullable=False)

    memberships = scheduler_db.relationship(
        "GroupMember",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    @classmethod
    def get_or_create_from_oauth(cls, user_info):
        email = user_info.get("email")
        name = user_info.get("name")

        if not email or not name:
            return None

        user = cls.query.filter_by(email=email).first()
        if not user:
            user = cls(email=email, name=name)
            scheduler_db.session.add(user)
            scheduler_db.session.commit()

        return user
