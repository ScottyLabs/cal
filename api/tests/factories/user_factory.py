import pytest

from app.models.models import User


@pytest.fixture
def user_factory(db):
    def create_user(**kwargs):
        user = User(
            email=kwargs.pop("email", "user@test.com"),
            oidc_sub=kwargs.pop("oidc_sub", None),
            **kwargs,
        )
        db.add(user)
        db.flush()
        return user

    return create_user
