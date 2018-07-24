'''
1. Read from benchmarking dataset (use argument?)
2. detect and aligned all face
    - save original face coordinate
    saved_data = aligned_face (np.array of uint8), koordinat wajah asli
3. Predict using the model
    - run model.preprocess
    - run model.predict (use saved weight)
    - map the prediction (from np_utils.to_categorical format, use numpy argmax)
4. Save predicted result, measure 
5. Visualize the result
    - use bounding box
    - put text (age, gender)
'''
import argparse, os, glob, cv2, dlib
import pandas as pd 
import numpy as np
from tqdm import tqdm
from keras import backend as K
from model import AgenderNetVGG16, AgenderNetInceptionV3, AgenderNetXception


def get_data_list(path='UTKface'):
    """
    Get list of image from UTKface dataset to be loaded later

    Parameters
    ----------
    path        : str
        Path to UTKface folder
    
    Returns
    -------
    image_list   : list
        List of image's paths
    """
    image_list = []
    for i in range(1,4):
        image_list.extend(glob.glob(os.path.join(path, 'part{}/*.jpg'.format(i))))
    return image_list


def make_db(paths):
    """
    Create database from list of image's path

    Parameters
    ----------
    paths       : list
        List of image's path from UTKface dataset
    
    Returns
    -------
    result      : pandas DataFrame
        DataFrame contain age, gender, and image (in numpy.uint8 array)
    """
    result = dict()
    print('[PREP] Building database...')
    age = [int(path.split('/')[-1].split('_')[0]) for path in tqdm(paths)]
    gender = [int(path.split('/')[-1].split('_')[1]) ^ 1 for path in tqdm(paths)] # '^' => UTKface use different code for gender
    img = [cv2.imread(path) for path in tqdm(paths)]
    
    result['image'] = img
    result['full_path'] = paths
    result['age'] = age
    result['gender'] = gender
    
    result = pd.DataFrame(data=result, 
                        columns=['image', 'full_path', 'age', 'gender'])
    return result


def get_one_aligned_face(image,
                    padding=0.4,
                    size=140,
                    predictpath='shape_predictor_5_face_landmarks.dat'):
    """
    Get aligned face from a image using dlib

    Parameters
    ----------
    image   : numpy array -> with dtype uint8 and shape (W, H, 3)
        Image to be used in alignment
    padding     : float
        Padding to be applied around aligned face
    size        : int
        Size of aligned_face to be returned
    predictpath   : str
        Path to predictor being used to get facial landmark (5 points, 68 points, etc)
    
    Returns
    ----------
    aligned face    : numpy array -> with dtype uint8 and shape (H, W, 3)
        if detect only 1 face
            return aligned face
        else
            return resized image
    position        : dict
        Dictionary of left, top, right, and bottom position from face
    """
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(predictpath)
    rects = detector(image, 1)

    aligned = None
    position = None
    if len(rects == 1):     # detect 1 face
        shape = predictor(image, rects[0])
        aligned = dlib.get_face_chip(image, shape, padding=padding, size=size)
        position = {'left'  : rects[0].left(),
                    'top'   : rects[0].top(),
                    'right' : rects[0].right(),
                    'bottom': rects[0].bottom()}
    else :
        aligned = resizeImage(image, size=size)
        position = {'left'  : 0,
                    'top'   : 0,
                    'right' : image.shape[1],
                    'bottom': image.shape[0]}

    return aligned, position


def resize_image(image,
                size=140):
    """
    Resize image and make it square

    Parameters
    ----------
    image       : numpy array -> with dtype uint8 and shape (W, H, 3)
        Image to be resized
    size        : int
        Size of image after resizing
    
    Returns
    -------
    resized     : numpy array -> with dtype uint8 and shape (W, H, 3)
        Resized and squared image
    """
    BLACK = [0,0,0]
    h = image.shape[0]
    w = image.shape[1]
    if w < h:               # add border at right
        border = h - w
        image= cv2.copyMakeBorder(image,0,0,border,0,
                                cv2.BORDER_CONSTANT,value=BLACK)
    else:
        border = w - h      # add border at top
        image= cv2.copyMakeBorder(image,border,0,0,0,
                                cv2.BORDER_CONSTANT,value=BLACK)
    resized = cv2.resize(image, (size,size), 
                        interpolation = cv2.INTER_CUBIC)    
    return resized


def get_result(model, list_x):
    """
    Get prediction from model

    Parameters
    ----------
    model           : Keras Model instance
        Model to be used to make prediction
    list_x           : list
        List of aligned face
    
    Returns
    -------
    gender_predicted     : numpy array
        Gender prediction, encode 0=Female 1=Male
    age_predicted        : numpy array
        Age prediction in range [0, 100]
    """
    predictions = model.predict(list_x)
    gender_predicted = [np.argmax(prediction[0]) for prediction in predictions]
    age_predicted = [np.argmax(prediction[1]) for prediction in predictions]
    return np.array(gender_predicted), np.array(age_predicted)

def get_metrics(age_predicted, gender_predicted, age_true, gender_true):
    """
    Calculate the score for age and gender prediction

    Parameters
    ----------
    age_predicted       : numpy array
        Age prediction's result
    gender_predicted    : numpy array
        Gender prediction's result
    
    """
    gender_acc = (gender_predicted == gender_true).sum() / len(gender_predicted)
    age_mae = abs(age_predicted - age_true).sum() / len(age_predicted)
    
    return age_mae, gender_acc

def visualize(fullimage, result):
    pass

def main():
    pass