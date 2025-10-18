from flask_login import LoginManager

from .database import db
from .models import User

login_manager = LoginManager()
login_manager.login_view = "auth.login"


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    user = User.query.get(int(user_id))
    if user and user.lift_suspension_if_expired():
        db.session.add(user)
        db.session.commit()
    return user
