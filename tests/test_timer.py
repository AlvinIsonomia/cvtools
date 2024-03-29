# -*- encoding:utf-8 -*-
# @Time    : 2019/7/6 22:44
# @Author  : gfjiang
# @Site    : 
# @File    : test_timer.py
# @Software: PyCharm
import time

import cvtools


def test_timer_content(capsys):
    timer = cvtools.Timer()
    timer.tic()
    time.sleep(1)
    print('{:.3f}'.format(timer.toc()))
    out, _ = capsys.readouterr()
    assert abs(float(out) - 1) < 1e-2

