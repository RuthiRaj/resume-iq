import os
import firebase_admin
from firebase_admin import credentials, firestore, auth
from app.core.config import settings

_firebase_app = None


def get_firebase_app():
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    if not firebase_admin._apps:
        if settings.FIREBASE_CREDENTIALS_PATH and os.path.exists(settings.FIREBASE_CREDENTIALS_PATH):
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
            _firebase_app = firebase_admin.initialize_app(
                cred, {"projectId": settings.FIREBASE_PROJECT_ID}
            )
        else:
            _firebase_app = firebase_admin.initialize_app(
                options={"projectId": settings.FIREBASE_PROJECT_ID}
            )
    else:
        _firebase_app = firebase_admin.get_app()

    return _firebase_app


def get_firestore_client():
    get_firebase_app()
    return firestore.client()
