def test_can_import_and_build_graph():
    from findmyhome.workflow import build_graph

    g = build_graph()
    assert g is not None

