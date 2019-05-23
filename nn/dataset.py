from torch.utils.data import Dataset
from torchvision import transforms, utils
import json
import os
import torch
import numpy as np
import matplotlib.pyplot as plt
from skimage import io

ROOT = "./data/"


class ToTensor(object):
    """Convert ndarrays in sample to Tensors."""

    def __call__(self, image):
        

        #image = image.transpose((2, 0, 1))
        return image.convert('RGB')


class ImageCaloriesDataset(Dataset):

    def __init__(self, calories_file, image_dir, transform=transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize((224, 224)),
        transforms.ToTensor()
    ])):

        with open(ROOT + calories_file) as json_file:
            self.calorie_image_tuples = json.load(json_file)["data"]
        self.image_dir = ROOT + image_dir
        self.transform = transform

    def __len__(self):
        return len(self.calorie_image_tuples)

    def __getitem__(self, idx):
        element = self.calorie_image_tuples[idx]

        img_name = os.path.join(self.image_dir, element['name'])

        image = io.imread(img_name)
        kcal = np.array(element['kcal'], dtype=np.float32)

        sample = {'image': image, 'kcal': kcal}

        if self.transform:
            sample['image'] = self.transform(sample['image'])

        return sample

    @staticmethod
    def show_img_batch(sample_batched):
        images_batch, kcal_batch = sample_batched['image'], sample_batched['kcal']

        grid = utils.make_grid(images_batch)
        plt.imshow(grid.numpy().transpose((1, 2, 0)))

        plt.title('Samples')
