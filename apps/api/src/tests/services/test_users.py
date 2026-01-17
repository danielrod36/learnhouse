import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi import Request, HTTPException
from sqlmodel import Session
from src.db.users import UserCreate, PublicUser
from src.services.users.users import create_user, create_user_with_invite

class TestUsers:
    @pytest.fixture
    def mock_request(self):
        return Mock(spec=Request)

    @pytest.fixture
    def mock_db_session(self):
        return Mock(spec=Session)

    @pytest.fixture
    def mock_current_user(self):
        return Mock(spec=PublicUser)

    @pytest.fixture
    def mock_user_object(self):
        return UserCreate(
            email="test@example.com",
            username="testuser",
            password="password",
            first_name="Test",
            last_name="User"
        )

    @pytest.mark.asyncio
    async def test_create_user_invite_only_fails(self, mock_request, mock_db_session, mock_current_user, mock_user_object):
        with patch("src.services.users.users.get_org_join_mechanism", new_callable=AsyncMock) as mock_get_mech:
            mock_get_mech.return_value = "inviteOnly"

            with pytest.raises(HTTPException) as exc:
                await create_user(
                    request=mock_request,
                    db_session=mock_db_session,
                    current_user=mock_current_user,
                    user_object=mock_user_object,
                    org_id=1
                )

            assert exc.value.status_code == 403
            assert exc.value.detail == "You need an invite to join this organization"

    @pytest.mark.asyncio
    async def test_create_user_invite_only_allowed_with_flag(self, mock_request, mock_db_session, mock_current_user, mock_user_object):
        with patch("src.services.users.users.get_org_join_mechanism", new_callable=AsyncMock) as mock_get_mech, \
             patch("src.services.users.users.User.model_validate") as mock_validate, \
             patch("src.services.users.users.UserRead.model_validate") as mock_user_read_validate, \
             patch("src.services.users.users.rbac_check", new_callable=AsyncMock), \
             patch("src.services.users.users.select"), \
             patch("src.services.users.users.check_limits_with_usage"), \
             patch("src.services.users.users.UserOrganization"), \
             patch("src.services.users.users.increase_feature_usage"), \
             patch("src.services.users.users.send_account_creation_email"), \
             patch("src.services.users.users.security_hash_password"):

            mock_get_mech.return_value = "inviteOnly"

            # Setup mock user
            mock_user = Mock()
            mock_user.id = 1
            mock_user.email = "test@example.com"
            mock_user.username = "testuser"
            mock_user.dict.return_value = {}
            mock_validate.return_value = mock_user

            # Mock DB lookups to return None (no existing user/email)
            mock_exec = mock_db_session.exec
            mock_exec.return_value.first.side_effect = [
                Mock(), # Organization exists
                None,   # Username available
                None    # Email available
            ]

            await create_user(
                request=mock_request,
                db_session=mock_db_session,
                current_user=mock_current_user,
                user_object=mock_user_object,
                org_id=1,
                allow_invite_only=True
            )

            # Should not raise

    @pytest.mark.asyncio
    async def test_create_user_open_signup_succeeds(self, mock_request, mock_db_session, mock_current_user, mock_user_object):
        with patch("src.services.users.users.get_org_join_mechanism", new_callable=AsyncMock) as mock_get_mech, \
             patch("src.services.users.users.User.model_validate") as mock_validate, \
             patch("src.services.users.users.UserRead.model_validate") as mock_user_read_validate, \
             patch("src.services.users.users.rbac_check", new_callable=AsyncMock), \
             patch("src.services.users.users.select"), \
             patch("src.services.users.users.check_limits_with_usage"), \
             patch("src.services.users.users.UserOrganization"), \
             patch("src.services.users.users.increase_feature_usage"), \
             patch("src.services.users.users.send_account_creation_email"), \
             patch("src.services.users.users.security_hash_password"):

            mock_get_mech.return_value = "open"

            # Setup mock user
            mock_user = Mock()
            mock_user.id = 1
            mock_user.email = "test@example.com"
            mock_user.username = "testuser"
            mock_user.dict.return_value = {}
            mock_validate.return_value = mock_user

            # Mock DB lookups to return None (no existing user/email)
            mock_exec = mock_db_session.exec
            mock_exec.return_value.first.side_effect = [
                Mock(), # Organization exists
                None,   # Username available
                None    # Email available
            ]

            await create_user(
                request=mock_request,
                db_session=mock_db_session,
                current_user=mock_current_user,
                user_object=mock_user_object,
                org_id=1
            )

            # Should not raise

    @pytest.mark.asyncio
    async def test_create_user_with_invite_open_org_fails(self, mock_request, mock_db_session, mock_current_user, mock_user_object):
        with patch("src.services.users.users.get_org_join_mechanism", new_callable=AsyncMock) as mock_get_mech:

            mock_get_mech.return_value = "open"

            with pytest.raises(HTTPException) as exc:
                await create_user_with_invite(
                    request=mock_request,
                    db_session=mock_db_session,
                    current_user=mock_current_user,
                    user_object=mock_user_object,
                    org_id=1,
                    invite_code="code"
                )

            assert exc.value.status_code == 403
            assert exc.value.detail == "This organization does not require an invite code"
