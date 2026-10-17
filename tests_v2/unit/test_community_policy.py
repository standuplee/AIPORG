from app.collectors.community.policy import DEFAULT_CONFIG_PATH, load_policies


def test_load_policies_reads_the_shared_config_file_and_defaults_to_disabled() -> None:
    policies = load_policies()

    assert DEFAULT_CONFIG_PATH.name == "community.yaml"
    expected_sites = {"dcinside", "clien", "fmkorea", "theqoo", "ruliweb"}
    assert expected_sites <= policies.keys()
    for name in expected_sites:
        # The operator-review safety gate from 1.0: every shipped site
        # defaults to disabled until someone flips it on in the YAML file.
        assert policies[name].enabled is False


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
