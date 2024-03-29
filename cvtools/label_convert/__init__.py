# -*- coding:utf-8 -*-
# author   : gfjiangly
# time     : 2019/7/10 16:12
# e-mail   : jgf0719@foxmail.com
# software : PyCharm

from .dota_to_coco import DOTA2COCO
from .arcsoft import (rect_reserved, face_reserved, head_reserved, gender_reserved)


__all__ = ['DOTA2COCO',
           'rect_reserved', 'face_reserved', 'head_reserved', 'gender_reserved']
