from unittest.mock import patch

import pytest
from sarc_mocks import fake_mymila_data, fake_raw_ldap_data

import sarc.account_matching.make_matches
import sarc.ldap.acquire
import sarc.ldap.mymila  # will monkeypatch "read_my_mila"
import sarc.ldap.read_mila_ldap  # will monkeypatch "query_ldap"
from sarc.config import MyMilaConfig, config
from sarc.ldap.api import get_user, get_users


@pytest.mark.usefixtures("empty_read_write_db")
def test_acquire_ldap(patch_return_values, mock_file):
    """
    Override the LDAP queries.
    Have users with matches to do.
        (at least we don't need to flex `perform_matching` with edge cases)
    Inspect the results in the database to make sure they're all there.
    """
    nbr_users = 10

    patch_return_values(
        {
            "sarc.ldap.read_mila_ldap.query_ldap": fake_raw_ldap_data(nbr_users),
            "sarc.ldap.mymila.query_mymila_csv": [],
        }
    )

    # Patch the built-in `open()` function for each file path
    with patch("builtins.open", side_effect=mock_file):
        sarc.ldap.acquire.run()

    # Validate the results of all of this by inspecting the database.
    for i in range(3):
        js_user = get_user(mila_email_username=f"john.smith{i:03d}@mila.quebec")
        assert js_user is not None
        # L = list(
        #    cfg.mongo.database_instance[cfg.ldap.mongo_collection_name].find(
        #        {"mila_ldap.mila_email_username": f"john.smith{i:03d}@mila.quebec"}
        #    )
        # )

        # test some drac_roles and drac_members fields
        js_user_d = js_user.dict()
        print(i, js_user_d)
        for segment in ["drac_roles", "drac_members"]:
            assert segment in js_user_d
            assert js_user_d[segment] is not None
            assert "email" in js_user_d[segment]
            assert js_user_d[segment]["email"] == f"js{i:03d}@yahoo.ca"
            assert "username" in js_user_d[segment]
            assert js_user_d[segment]["username"] == f"john.smith{i:03d}"

        assert js_user.name == js_user.mila_ldap["display_name"]

        assert js_user.mila.email == js_user.mila_ldap["mila_email_username"]
        assert js_user.mila.username == js_user.mila_ldap["mila_cluster_username"]
        assert js_user.mila.active

        assert js_user.drac.email == js_user.drac_members["email"]
        assert js_user.drac.username == js_user.drac_members["username"]
        assert js_user.drac.active

        if i == 1:
            assert js_user_d["mila_ldap"]["supervisor"] is not None

    # test the absence of the mysterious stranger
    js_user = get_user(drac_account_username="ms@hotmail.com")
    assert js_user is None


@pytest.mark.usefixtures("empty_read_write_db")
def test_merge_ldap_and_mymila(patch_return_values, mock_file):
    cfg: MyMilaConfig = config().mymila
    nbr_users = 20
    nbr_profs = 10
    ld_users = fake_raw_ldap_data(nbr_users)

    patch_return_values(
        {
            "sarc.ldap.read_mila_ldap.query_ldap": fake_raw_ldap_data(nbr_users),
            "sarc.ldap.mymila.query_mymila_csv": fake_mymila_data(nbr_users, nbr_profs),
        }
    )

    # Patch the built-in `open()` function for each file path
    with patch("builtins.open", side_effect=mock_file):
        sarc.ldap.acquire.run()

    users = get_users()
    assert len(users) == nbr_users

    for user, ld_user in zip(users, ld_users):
        assert user.mila_ldap["display_name"] != ld_user["displayName"]

        if user.prof["membership_type"]:
            assert (
                user.collaborator["collaboration_type"]
                not in cfg.collaborators_affiliations.values()
            )
    for i in range(nbr_profs):
        user = users[i]
        # A prof should not have a supervisor or co-supervisor but there's a
        # mismatch between the number of profs in ldap (1) and the generated
        # mymila data (5)
        # assert user.mila_ldap["supervisor"] is None
        # assert user.mila_ldap["co_supervisor"] is None

    for i in range(nbr_profs, nbr_users):
        user = users[i]
        assert (
            user.mila_ldap["supervisor"] == f"john.smith{i%nbr_profs:03d}@mila.quebec"
        )
        assert (
            user.mila_ldap["co_supervisor"]
            == f"john.smith{(i+1)%nbr_profs:03d}@mila.quebec"
        )

    # TODO: Add checks for fields coming from mymila now saved in DB
