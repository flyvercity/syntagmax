from syntagmax.utils import get_execution_plan


def test_dag():
    full_graph = {
        'Deploy': {'Build', 'Test'},
        'Build': {'Lint'},
        'Test': {'Build'},
        'Lint': set(),
        'Cleanup': {'Deploy'},
    }

    plan = get_execution_plan(full_graph, 'Deploy')
    print(f"Plan for 'Deploy': {plan}")
    assert plan == ['Lint', 'Build', 'Test', 'Deploy']
