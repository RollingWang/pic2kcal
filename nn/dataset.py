from torch.utils.data import Dataset
from torchvision import transforms
import json
import os
import numpy as np
from skimage import io


def transform_data(element):
    return np.array([element], dtype=np.float32)


food_image_transform = transforms.Compose(
    [
        transforms.ToPILImage(),
        # transforms.Resize((224, 224)),
        transforms.RandomResizedCrop(224, scale=(0.7, 1.0), ratio=(0.9, 1.1)),
        transforms.RandomHorizontalFlip(),
        # transforms.Resize((224, 224)),
        # imageNet normalization
        transforms.ToTensor(),
        # TODO: re add this normalization. only disabled because we probably have a bug with the tensorboard visualization somewhere
        # transforms.Normalize(
        #   mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
        # ),
    ]
)


class FoodDataset(Dataset):
    def __init__(self, *, calories_file, image_dir):
        print(f"loading {calories_file}")
        with open(calories_file) as json_file:
            self.data = json.load(json_file)
            self.calorie_image_tuples = self.data["data"]
            self.ingredient_names = self.data["ingredient_names"]
        print(f"loading {calories_file} done")
        self.image_dir = image_dir
        self.transform = food_image_transform

    def __len__(self):
        return len(self.calorie_image_tuples)

    def __getitem__(self, idx):
        # print("getitem", idx)
        element = self.calorie_image_tuples[idx]

        img_name = os.path.join(self.image_dir, element["name"])

        sample = {"fname": element["name"], "image": io.imread(img_name)}

        for key in ["kcal", "protein", "fat", "carbohydrates", "mass_per_portion"]:
            value = transform_data(element[key])
            sample[key] = value

        sample["ingredients"] = np.array(element["ingredients"], dtype=np.float32)

        if self.transform:
            sample["image"] = self.transform(sample["image"])

        return sample
