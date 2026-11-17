from streamlit.testing.v1 import AppTest

from normalizer import ROOT


def test_app_filters_and_user_input():
    app = AppTest.from_file(str(ROOT / "main.py"), default_timeout=90).run()
    assert not app.exception
    assert app.metric[0].value == "3000"
    app.sidebar.multiselect[0].set_value(["motor"]).run()
    assert not app.exception
    assert app.metric[0].value == "360"
    app.text_area[0].set_value("mot. c/ flga no mancl")
    app.button[0].click().run()
    assert not app.exception
    assert any("folga" in element.value for element in app.markdown)
    app.text_area[0].set_value("   ")
    app.button[0].click().run()
    assert not app.exception
    assert any("Digite um relato" in message.value for message in app.warning)
