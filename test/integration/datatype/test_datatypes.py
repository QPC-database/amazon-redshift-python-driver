import configparser
import os
import typing
from math import isclose
from test.integration.datatype._generate_test_datatype_tables import (  # type: ignore
    DATATYPES_WITH_MS,
    FLOAT_DATATYPES,
    Datatypes,
    datatype_test_setup,
    datatype_test_teardown,
    get_table_name,
    redshift_test_data,
    test_data,
)

import pytest  # type: ignore

import redshift_connector
from redshift_connector.config import ClientProtocolVersion

conf = configparser.ConfigParser()
root_path = os.path.dirname(os.path.dirname(os.path.abspath(os.path.join(__file__, os.pardir))))
conf.read(root_path + "/config.ini")


@pytest.fixture(scope="session", autouse=True)
def create_datatype_test_resources(request):
    """
    Creates datatype test schema, tables, and inserts test data.
    """
    datatype_test_setup(conf)

    def fin():
        datatype_test_teardown(conf)

    request.addfinalizer(fin)


@pytest.mark.skip(reason="manual")
@pytest.mark.parametrize("datatype", Datatypes.list())
@pytest.mark.parametrize("client_protocol", ClientProtocolVersion.list())
def test_datatype_recv_support(db_kwargs, datatype, client_protocol):
    db_kwargs["client_protocol_version"] = client_protocol
    table_name: str = get_table_name(datatype)
    exp_results: typing.Tuple[typing.Tuple[str, ...], ...] = test_data[datatype.name]

    with redshift_connector.connect(**db_kwargs) as con:
        assert con._client_protocol_version == client_protocol
        with con.cursor() as cursor:
            cursor.execute("select * from {}".format(table_name))
            results = cursor.fetchall()

            assert results is not None
            assert len(results) == len(exp_results)

            for ridx, exp_row in enumerate(exp_results):
                assert results[ridx][0] == exp_row[0]

                # the expected Python value is stored in the last index of the tuple
                if datatype in FLOAT_DATATYPES:
                    assert isclose(
                        typing.cast(float, results[ridx][1]),
                        typing.cast(float, exp_row[-1]),
                        rel_tol=1e-05,
                        abs_tol=1e-08,
                    )

                elif datatype in DATATYPES_WITH_MS:
                    assert results[ridx][1].replace(microsecond=0) == exp_row[-1].replace(microsecond=0)
                    assert isclose(results[ridx][1].microsecond, exp_row[-1].microsecond, rel_tol=1e1)
                else:
                    assert results[ridx][1] == exp_row[-1]


redshift_datatype_testcases: typing.List[typing.Tuple] = []
for datatype in redshift_test_data:
    for test_case in redshift_test_data[datatype]:
        redshift_datatype_testcases.append((datatype, test_case))


@pytest.mark.skip(reason="manual")
@pytest.mark.parametrize("client_protocol", ClientProtocolVersion.list())
@pytest.mark.parametrize("_input", redshift_datatype_testcases)
def test_redshift_specific_recv_support(db_kwargs, _input, client_protocol):
    db_kwargs["client_protocol_version"] = client_protocol
    datatype, data = _input
    test_val, exp_val = data

    with redshift_connector.connect(**db_kwargs) as con:
        with con.cursor() as cursor:
            cursor.execute("select {}".format(test_val))
            results: typing.Tuple = cursor.fetchall()
            assert len(results) == 1
            assert len(results[0]) == 1
            assert results[0][0] == exp_val
