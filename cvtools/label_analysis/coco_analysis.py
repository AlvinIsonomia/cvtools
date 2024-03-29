# -*- coding:utf-8 -*-
# author   : gfjiangly
# time     : 2019/6/24 9:57
# e-mail   : jgf0719@foxmail.com
# software : PyCharm
import copy
import cv2
import os.path as osp
import numpy as np
from tqdm import tqdm
from collections import defaultdict

import cvtools
from cvtools.label_analysis.crop_in_order import CropInOder


class COCOAnalysis(object):
    """coco-like datasets analysis"""
    def __init__(self, img_prefix, ann_file=None):
        self.img_prefix = img_prefix
        if ann_file is not None:
            self.ann_file = ann_file
            self.coco_dataset = cvtools.load_json(ann_file)
            self.COCO = cvtools.COCO(ann_file)
            self.catToAnns = defaultdict(list)
            if 'annotations' in self.coco_dataset:
                for ann in self.coco_dataset['annotations']:
                    self.catToAnns[ann['category_id']].append(ann)

    def stats_size(self):
        # TODO: 统计不同大小的实例比例
        #  for small objects: area < 32^2
        #  for medium objects: 32^2 < area < 96^2
        #  for large objects: area > 96^2
        #  see http://cocodataset.org/#detection-eval and https://arxiv.org/pdf/1405.0312.pdf
        pass

    def stats_num(self, save='stats_num.json'):
        total_anns = 0
        imgToNum = defaultdict()
        for cat_id, ann_ids in self.COCO.catToImgs.items():
            imgs = set(ann_ids)
            total_anns += len(ann_ids)
            assert len(imgs) > 0
            imgToNum[self.COCO.cats[cat_id]['name']] = len(ann_ids) / float(len(imgs))
        imgToNum['total'] = total_anns / float(len(self.COCO.imgs))
        print(imgToNum)
        cvtools.save_json(imgToNum, save)

    def cluster_analysis(self, save_root, name_clusters=('bbox', ), n_clusters=(3,), by_cat=False):
        if by_cat:
            self._cluster_by_cat(save_root, name_clusters, n_clusters)
        assert len(name_clusters) == len(n_clusters)
        image_ids = self.COCO.getImgIds()
        image_ids.sort()
        roidb = copy.deepcopy(self.COCO.loadImgs(image_ids))
        print('roidb: {}'.format(len(roidb)))
        cluster_dict = defaultdict(list)
        for entry in roidb:
            ann_ids = self.COCO.getAnnIds(imgIds=entry['id'], iscrowd=None)
            objs = self.COCO.loadAnns(ann_ids)
            # Sanitize bboxes -- some are invalid
            for obj in objs:
                if 'ignore' in obj and obj['ignore'] == 1:
                    continue
                if 'area' in name_clusters:
                    cluster_dict['area'].append(obj['area'])
                if 'w-vs-h' in name_clusters:
                    cluster_dict['w-vs-h'].append(obj['bbox'][2] / float(obj['bbox'][3]))
        cvtools.makedirs(save_root)
        print('start cluster analysis...')
        for i, cluster_name in enumerate(cluster_dict.keys()):
            cluster_value = cluster_dict[cluster_name]
            assert len(cluster_value) >= n_clusters[i]
            value_arr = np.array(cluster_value)
            percent = np.percentile(value_arr, [1, 50, 99])
            value_arr = value_arr[percent[2] > value_arr]
            cvtools.draw_hist(value_arr, bins=1000, x_label=cluster_name, y_label="Quantity",
                              title=cluster_name, density=False,
                              save_name=osp.join(save_root, cluster_name+'.png'))
            cluster_value = np.array(value_arr).reshape(-1, 1)
            cluster_value_centers = cvtools.DBSCAN_cluster(cluster_value, metric='manhattan')
            np.savetxt(osp.join(save_root, cluster_name+'.txt'),
                       np.around(cluster_value_centers, decimals=0))
        print('cluster analysis finished!')

    def _cluster_by_cat(self, save_root, name_clusters=('bbox', ), n_clusters=(3,)):
        assert len(name_clusters) == len(n_clusters)
        cluster_dict = defaultdict(lambda: defaultdict(list))
        for key, ann in self.COCO.anns.items():
            cat_name = self.COCO.cats[ann['category_id']]['name']
            if 'area' in name_clusters:
                cluster_dict[cat_name]['area'].append(ann['area'])
            if 'w-vs-h' in name_clusters:
                cluster_dict[cat_name]['w-vs-h'].append(ann['bbox'][2] / float(ann['bbox'][3]))
        cvtools.makedirs(save_root)
        for cat_name, cluster_value in cluster_dict.items():
            cluster_values = cluster_dict[cat_name]
            cluster_results = defaultdict(lambda: defaultdict(list))
            for i, cluster_name in enumerate(cluster_values.keys()):
                if len(cluster_value) < n_clusters[i]:
                    continue
                centers = cvtools.k_means_cluster(np.array(cluster_value).reshape(-1, 1),
                                                  n_clusters=n_clusters[i])
                cluster_results[cluster_name][cat_name].append(list(centers.reshape(-1)))
            cvtools.save_json(cluster_results, osp.join(save_root, 'cluster_{}.json'.format(cat_name)))

    def stats_class_distribution(self, save_file):
        cls_to_num = dict()
        draw_cats = []
        for cat_id in self.COCO.catToImgs:
            cat_name = self.COCO.cats[cat_id]['name']
            cat_num = len(self.COCO.catToImgs[cat_id])
            draw_cats += [cat_name] * cat_num
            cls_to_num[cat_name] = cat_num
        cls_to_num = dict(sorted(cls_to_num.items(), key=lambda item: item[1]))
        cvtools.write_key_value(cls_to_num, save_file)
        cvtools.draw_class_distribution(draw_cats, save_name=save_file.replace('txt', 'png'))

    def vis_instances(self, save_root, vis='bbox', box_format='x1y1wh', by_cat=False):
        if by_cat:
            self._vis_instances_by_cat(save_root, vis, box_format)
        image_ids = self.COCO.getImgIds()
        image_ids.sort()
        if cvtools._DEBUG:
            roidb = copy.deepcopy(self.COCO.loadImgs(image_ids))[:10]
        else:
            roidb = copy.deepcopy(self.COCO.loadImgs(image_ids))
        print('{} images.'.format(len(roidb)))
        cvtools.makedirs(save_root)
        for i, entry in enumerate(roidb):
            print('Visualize image %d of %d: %s' % (i, len(roidb), entry['file_name']))
            image_name = entry['file_name']
            image_file = osp.join(self.img_prefix, image_name)
            img = cvtools.imread(image_file)
            image_name = osp.splitext(image_name)[0]
            if 'crop' in entry:
                img = img[entry['crop'][1]:entry['crop'][3], entry['crop'][0]:entry['crop'][2]]
                image_name = '_'.join([image_name] + list(map(str, entry['crop'])))
            if img is None:
                print('{} is None.'.format(image_file))
                continue
            ann_ids = self.COCO.getAnnIds(imgIds=entry['id'], iscrowd=None)
            objs = self.COCO.loadAnns(ann_ids)
            if len(objs) == 0:
                continue
            # Sanitize bboxes -- some are invalid
            for obj in objs:
                vis_obj = []
                if 'ignore' in obj and obj['ignore'] == 1:
                    continue
                if vis in obj:
                    vis_obj = obj[vis]
                class_name = self.COCO.cats[obj['category_id']]['name'] if 'category_id' in obj else ''
                img = cvtools.draw_boxes_texts(img, vis_obj, class_name, box_format=box_format)
            # save in jpg format for saving storage
            cvtools.imwrite(img, osp.join(save_root, image_name + '.jpg'))

    def _vis_instances_by_cat(self, save_root, vis_cats=None, vis='bbox', box_format='x1y1wh'):
        catImgs = copy.deepcopy(self.COCO.catToImgs)
        catImgs = {cat: set(catImgs[cat]) for cat in catImgs}
        for cat_id, image_ids in catImgs.items():
            cat_name = self.COCO.cats[cat_id]['name']
            if vis_cats is not None and cat_name not in vis_cats:
                continue
            print('Visualize %s' % cat_name)
            if cvtools._DEBUG:
                roidb = copy.deepcopy(self.COCO.loadImgs(image_ids))[:10]
            else:
                roidb = copy.deepcopy(self.COCO.loadImgs(image_ids))
            for i, entry in enumerate(roidb):
                print('Visualize image %d of %d: %s' % (i, len(roidb), entry['file_name']))
                image_name = entry['file_name']
                image_file = osp.join(self.img_prefix, image_name)
                img = cv2.imdecode(np.fromfile(image_file, dtype=np.uint8), cv2.IMREAD_COLOR)  # support chinese
                # img = cv2.imread(image_file)  # not support chinese
                image_name = osp.splitext(image_name)[0]
                if 'crop' in entry:
                    img = img[entry['crop'][1]:entry['crop'][3], entry['crop'][0]:entry['crop'][2]]
                    image_name = '_'.join([image_name] + list(map(str, entry['crop'])))
                if img is None:
                    print('{} is None.'.format(image_file))
                    continue
                ann_ids = self.COCO.getAnnIds(imgIds=entry['id'], iscrowd=None)
                objs = self.COCO.loadAnns(ann_ids)
                for obj in objs:
                    if obj['category_id'] != cat_id:
                        continue
                    if 'ignore' in obj and obj['ignore'] == 1:
                        continue
                    vis_obj = []
                    if vis in obj:
                        vis_obj = obj[vis]
                    class_name = [cat_name if 'category_id' in obj else '']
                    img = cvtools.draw_boxes_texts(img, vis_obj, class_name, box_format=box_format)
                # save in jpg format for saving storage
                cvtools.imwrite(img, osp.join(save_root, cat_name, image_name + '.jpg'))

    def crop_in_order_with_label(self, save_root, w=1920, h=1080, overlap=0.):
        assert 1920 >= w >= 800 and 1080 >= h >= 800 and 0.5 >= overlap >= 0.
        crop = CropInOder(width_size=w, height_size=h, overlap=overlap)
        image_ids = self.COCO.getImgIds()
        image_ids.sort()
        if cvtools._DEBUG:
            roidb = copy.deepcopy(self.COCO.loadImgs(image_ids))[:10]
        else:
            roidb = copy.deepcopy(self.COCO.loadImgs(image_ids))
        print('{} images.'.format(len(roidb)))

        cvtools.makedirs(save_root+'/images')
        cvtools.makedirs(save_root+'/labelTxt+crop')

        for entry in tqdm(roidb):
            if cvtools._DEBUG:
                print('crop {}'.format(entry['file_name']))
            image_name = entry['file_name']
            image_file = osp.join(self.img_prefix, image_name)
            img_name_no_suffix, img_suffix = osp.splitext(image_name)
            img = cv2.imdecode(np.fromfile(image_file, dtype=np.uint8), cv2.IMREAD_COLOR)  # support chinese
            # img = cv2.imread(image_file)  # not support chinese
            if img is None:
                print('{} is None.'.format(image_file))
                continue
            ann_ids = self.COCO.getAnnIds(imgIds=entry['id'], iscrowd=None)
            objs = self.COCO.loadAnns(ann_ids)
            boxes = [obj['bbox'] for obj in objs]
            # labels = [obj['category_id'] for obj in objs]
            if len(boxes) == 0:
                continue
            crop_imgs, starts, new_ann_ids = crop(img, np.array(boxes), np.array(ann_ids))
            # crops = []
            for crop_i, crop_img in enumerate(crop_imgs):
                # new_img_name = img_name + '_' + str(crop_i) + img_suffix
                # cv2.imwrite(os.path.join(save_root, 'images', new_img_name), crop_img)
                sx, sy = starts[crop_i]
                h, w, _ = crop_img.shape
                ex, ey = sx + w, sy + h
                # crops.append([sx+3, sy+3, ex-3, ey-3])
                txt_name = '_'.join([img_name_no_suffix] +
                                    [str(crop_i)]+list(map(str, [sx, sy, ex, ey]))) + '.txt'
                txt_content = ''
                crop_objs = self.COCO.loadAnns(new_ann_ids[crop_i])
                if len(crop_objs) == 0:
                    continue
                crop_segs = np.array([crop_obj['segmentation'][0] for crop_obj in crop_objs])
                # filter_segs = []
                temp1 = np.any(crop_segs < 0., axis=1)
                filter_segs = crop_segs[np.any(crop_segs > w, axis=1)]
                # filter_segs.append(crop_segs[np.any(crop_segs > w, axis=1)])
                if len(filter_segs) > 0:
                    pass
                # for crop_obj in crop_objs:
                #     polygen = np.array(crop_obj['segmentation'][0]).reshape(-1, 2)
                #     polygen = polygen - np.array(starts[crop_i]).reshape(-1, 2)
                #     temp1 = np.any(polygen < 0., axis=1)
                #     temp = polygen[temp1]
                #     if len(temp) > 0:
                #         pass
                #     line = list(map(str, polygen.reshape(-1)))
                #     cat = self.COCO.cats[crop_obj['category_id']]['name']
                #     diffcult = str(crop_obj['difficult'])
                #     line.append(cat)
                #     line.append(diffcult)
                #     txt_content += ' '.join(line) + '\n'
                # cvtools.strwrite(txt_content, osp.join(save_root, 'labelTxt+crop', txt_name))
            # if len(crops) > 0:
            #     draw_img = cvtools.draw_boxes_texts(img, crops, line_width=3, box_format='x1y1x2y2')
            #     cvtools.imwrite(draw_img, osp.join(save_root, 'images', img_name_no_suffix+'.jpg'))

    def crop_in_order_for_test(self, save, w=1920, h=1080, overlap=0.):
        assert 1920 >= w >= 800 and 1080 >= h >= 800 and 0.5 >= overlap >= 0.
        from collections import defaultdict
        imgs = cvtools.get_images_list(self.img_prefix)
        crop = CropInOder(width_size=w, height_size=h, overlap=overlap)
        self.test_dataset = defaultdict(list)
        for image_file in tqdm(imgs):
            if cvtools._DEBUG:
                print('crop {}'.format(image_file))
            image_name = osp.basename(image_file)
            img = cvtools.imread(image_file)  # support chinese
            if img is None:
                print('{} is None.'.format(image_file))
                continue
            crop_imgs, starts, _ = crop(img)
            for crop_img, start in zip(crop_imgs, starts):
                crop_rect = start[0], start[1], start[0]+crop_img.shape[1], start[1]+crop_img.shape[0]
                self.test_dataset[image_name].append(crop_rect)
        cvtools.save_json(self.test_dataset, save)


if __name__ == '__main__':
    img_prefix = 'D:/data/rssrai2019_object_detection/train/images'
    ann_file = '../label_convert/dota/train_dota_x1y1wh_polygen.json'
    coco_analysis = COCOAnalysis(img_prefix, ann_file)

    # coco_analysis.stats_num('dota/num_per_img.json')

    coco_analysis.crop_in_order_with_label('dota/crop800x800/val', w=800., h=800., overlap=0.1)

    # save = 'dota/test_crop800x800_dota_x1y1wh_polygen.json'
    # coco_analysis.crop_in_order_for_test(save, w=800, h=800, overlap=0.1)

    # coco_analysis.vis_instances('dota/vis_dota_whole/', vis='segmentation', box_format='x1y1x2y2x3y3x4y4')

    # coco_analysis.split_dataset(to_file='Arcsoft/gender_elevator/gender_elevator.json', val_size=1./3.)
    # coco_analysis.stats_class_distribution('dota/class_distribution/class_distribution.txt')

    # coco_analysis.cluster_analysis('dota/bbox_distribution/', name_clusters=('area',), n_clusters=(18,))

    # img_prefix = 'F:/data/detection/20181208_head_labeling'
    # ann_file = '../label_convert/arcsoft/20181208_head_labeling.json'
    # coco_analysis = COCOAnalysis(img_prefix, ann_file)
    # coco_analysis.vis_boxes('arcsoft/vis_box/', vis='bbox', box_format='x1y1wh')

