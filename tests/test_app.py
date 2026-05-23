from app import main


def test_main_prints_app_name(capsys) -> None:
    main()

    captured = capsys.readouterr()
    assert "Bot-Formadores MVP" in captured.out
