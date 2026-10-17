from app.collectors.community.policy import DEFAULT_CONFIG_PATH, load_policies


def test_load_policies_reads_the_shared_config_file() -> None:
    policies = load_policies()

    assert DEFAULT_CONFIG_PATH.name == "community.yaml"
    expected_sites = {"dcinside", "clien", "fmkorea", "theqoo", "ruliweb"}
    assert expected_sites <= policies.keys()
    # 2026-10-17: operator reviewed each site's robots.txt live and decided
    # to enable all five (config/community.yaml records the decision date
    # inline). The "defaults to disabled until reviewed" safety gate itself
    # is covered below by a fresh, never-reviewed site instead of asserting
    # a specific state of the shared file, which is expected to change as
    # the operator's own decisions change.
    for name in expected_sites:
        assert isinstance(policies[name].enabled, bool)


def test_site_policy_matches_domain_and_subdomains() -> None:
    policies = load_policies()
    clien = policies["clien"]

    assert clien.matches_domain("www.clien.net")
    assert clien.matches_domain("clien.net")
    assert not clien.matches_domain("notclien.net")


def test_site_policy_exclude_patterns_match_login_and_member_paths() -> None:
    policies = load_policies()
    dcinside = policies["dcinside"]

    assert dcinside.is_excluded("https://gall.dcinside.com/person/1234")
    assert not dcinside.is_excluded("https://gall.dcinside.com/board/view/?id=x&no=1")


def test_load_policies_defaults_an_unreviewed_site_to_disabled(tmp_path) -> None:
    config_path = tmp_path / "community.yaml"
    config_path.write_text(
        "sites:\n  newsite:\n    domains: [example.com]\n",
        encoding="utf-8",
    )

    policies = load_policies(config_path)

    # A site entry with no "enabled" key -- an operator who hasn't reviewed
    # it yet -- must default to disabled, not silently collect.
    assert policies["newsite"].enabled is False


def test_load_policies_applies_defaults_when_a_site_omits_a_field(tmp_path) -> None:
    config_path = tmp_path / "community.yaml"
    config_path.write_text(
        "defaults:\n"
        "  min_interval_sec: 7.0\n"
        "sites:\n"
        "  testsite:\n"
        "    enabled: true\n"
        "    domains: [example.com]\n",
        encoding="utf-8",
    )

    policies = load_policies(config_path)

    assert policies["testsite"].enabled is True
    assert policies["testsite"].min_interval_sec == 7.0
    assert policies["testsite"].search_hints == ("testsite",)
    assert policies["testsite"].exclude_patterns == ()
