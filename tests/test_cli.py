import pytest

from schemaflow.cli import main


def test_cli_long_form(capsys):
    # Test with long form arguments
    argv = ['--input', 'schema.json', '--output', 'output.ts']
    exit_code = main(argv)
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "Input schema: schema.json\nOutput file: output.ts"


def test_cli_short_form(capsys):
    # Test with short form arguments
    argv = ['-i', 'schema.json', '-o', 'output.ts']
    exit_code = main(argv)
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "Input schema: schema.json\nOutput file: output.ts"


def test_cli_mixed_form(capsys):
    # Test with mixed short and long forms
    argv = ['-i', 'schema.json', '--output', 'output.ts']
    exit_code = main(argv)
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "Input schema: schema.json\nOutput file: output.ts"


def test_cli_missing_input():
    # Test missing required input argument
    argv = ['--output', 'output.ts']
    with pytest.raises(SystemExit) as exc_info:
        main(argv)
    # argparse exits with code 2 on error
    assert exc_info.value.code == 2


def test_cli_missing_output():
    # Test missing required output argument
    argv = ['--input', 'schema.json']
    with pytest.raises(SystemExit) as exc_info:
        main(argv)
    assert exc_info.value.code == 2