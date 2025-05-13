import json
import jsonpath_ng

def test_di():
    with open("tests/testdata/atoms_di.json", "rt") as f:
        data = json.load(f)
    expr = jsonpath_ng.parse("atoms.*")
    res = expr.find(data)
    assert len(res) == 57
    assert str(res[0].path) == "ECW0"
    assert res[0].value == "4A67F6D5-32FC-4915-9534-2AA6072C3432,binary"
    assert str(res[56].path) == "_DIR"
    assert res[56].value == "04C13128-CED0-42AD-B9E8-E9ACEED95E23,binary"

def test_mc():
    with open("tests/testdata/atoms_mc.json", "rt") as f:
        data = json.load(f)
    expr = jsonpath_ng.parse("atoms.OPTIONDATA")
    res = expr.find(data)
    assert str(res[0].path) == "OPTIONDATA"
    assert res[0].value == "F78D3B2B-FC4C-41B3-8893-CE58B89F4EAB,binary"

def test_ps():
    with open("tests/testdata/atoms_pspark.json", "rt") as f:
        data = json.load(f)
    expr = jsonpath_ng.parse("atoms.Data")
    res = expr.find(data)
    assert len(res) == 1
    assert str(res[0].path) == "Data"
    assert res[0].value == "1C1CF2F3-4E77-44CD-BA21-402397DF4E13,binary"
