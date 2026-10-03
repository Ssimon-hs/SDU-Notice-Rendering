from server.sources.discovery import _source_id


def test_discovered_source_id_is_stable():
    assert _source_id("www.sps.sdu.edu.cn") == _source_id("www.sps.sdu.edu.cn")
    assert _source_id("www.sps.sdu.edu.cn").startswith("sdu-auto-")