"""
    MoinMoin - dataset tests

    @license: GNU GPL, see COPYING for details.
"""

import pytest

from MoinMoin.util.dataset import Column, DictDataset, TupleDataset


def test_tuple_dataset_iterator_protocol():
    dataset = TupleDataset()
    dataset.addRow(('first', 1))
    dataset.addRow(('second', 2))

    assert list(dataset) == [('first', 1), ('second', 2)]
    with pytest.raises(StopIteration):
        next(dataset)

    dataset.reset()
    assert next(dataset) == ('first', 1)


def test_dict_dataset_orders_values_by_columns():
    dataset = DictDataset()
    dataset.columns = [Column('name'), Column('count')]
    dataset.addRow({'count': 2, 'name': 'example'})

    assert list(dataset) == [('example', 2)]
