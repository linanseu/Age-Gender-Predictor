import os, pickle, cv2
import numpy as np
import pandas as pd
import tensorflow as tf
from model import AgenderNetVGG16, AgenderNetInceptionV3, AgenderNetXception, SSRNet, AgenderNetMobileNetV2
from keras.utils import np_utils
from sklearn.model_selection import KFold
from keras.callbacks import EarlyStopping, ModelCheckpoint
from keras.utils.training_utils import multi_gpu_model
from keras import backend as K
from keras import metrics
from keras.optimizers import Adam
import TYY_callbacks
import argparse
from generator import DataGenerator

parser = argparse.ArgumentParser()
parser.add_argument('--gpu',
					default=1, 
					type=int,
					help='Num of GPU')
parser.add_argument('--model',
					choices=['vgg16', 'inceptionv3', 'xception', 'ssrnet', 'mobilenetv2'],
					default='inceptionv3',
					help='Model to be used')
parser.add_argument('--trial',
					action='store_true',
					help='Run training to check code')
parser.add_argument('--epoch',
					default=50,
					type=int,
					help='Num of training epoch')
parser.add_argument('--batch_size',
					default=64,
					type=int,
					help='Size of data batch to be used')
parser.add_argument('--num_worker',
					default=4,
					type=int,
					help='Number of worker to process data')

def prepData(trial):
	wiki = pd.read_csv('dataset/wiki_cleaned.csv')
	imdb = pd.read_csv('dataset/imdb_cleaned.csv')
	adience = pd.read_csv('dataset/adience_cleaned.csv')
	data = pd.concat([wiki, imdb, adience], axis=0)
	del wiki, imdb, adience
	db = data['db_name'].values
	paths = data['full_path'].values
	ageLabel = np.array(data['age'], dtype='uint8')
	genderLabel = np.array(data['gender'], dtype='uint8')
	return db, paths, ageLabel, genderLabel

def fitModel(model, input_size, categorical,
			trainDb, trainPaths, trainAge, trainGender, 
			testDb, testPaths, testAge, testGender,
			epoch, batch_size, num_worker,
			callbacks, GPU):
	return model.fit_generator(
			DataGenerator(model, trainDb, trainPaths, trainAge, trainGender, batch_size, input_size, categorical),
			validation_data=DataGenerator(model, testDb, testPaths, testAge, testGender, batch_size, input_size, categorical),
			epochs=epoch, 
			verbose=2,
			steps_per_epoch=len(trainAge) // (batch_size * GPU),
			validation_steps=len(testAge) // (batch_size * GPU),
			workers=num_worker,
			use_multiprocessing=True,
			max_queue_size=int(batch_size * 2),
			callbacks=callbacks)

def mae(y_true, y_pred):
	return K.mean(K.abs(K.sum(K.cast(K.arange(0,101), dtype='float32') * y_pred, axis=1) - 
						K.sum(K.cast(K.arange(0,101), dtype='float32') * y_true, axis=1)), axis=-1)

def main():
	#dynamicaly allocate GPU memory
	config = tf.ConfigProto()
	config.gpu_options.allow_growth = True
	sess = tf.Session(config=config)
	K.tensorflow_backend.set_session(sess)

	args = parser.parse_args()
	GPU = args.gpu
	MODEL = args.model
	TRIAL = args.trial
	EPOCH = args.epoch
	BATCH_SIZE = args.batch_size
	NUM_WORKER = args.num_worker
	INPUT_SIZE = 64 if MODEL == 'ssrnet' else 140
	CATEGORICAL = False if MODEL == 'ssrnet' else True

	db, paths, ageLabel, genderLabel = prepData(TRIAL)

	n_fold = 1
	print('[K-FOLD] Started...')
	kf = KFold(n_splits=10, shuffle=True, random_state=1)
	kf_split = kf.split(ageLabel)
	for train_idx, test_idx in kf_split:
		print('[K-FOLD] Fold {}'.format(n_fold))
		model = None
		trainModel = None
		if GPU == 1:
			if MODEL == 'ssrnet':
				model = SSRNet(INPUT_SIZE, [3, 3, 3], 1.0, 1.0)
			elif MODEL == 'vgg16':
				model = AgenderNetVGG16()
			elif MODEL == 'inceptionv3':
				model = AgenderNetInceptionV3()
			elif MODEL == 'mobilenetv2':
				model = AgenderNetMobileNetV2()
			else :
				model = AgenderNetXception()
			# trainModel = model
		else :
			with tf.device("/cpu:0"):
				if MODEL == 'ssrnet':
					model = SSRNet(64, [3, 3, 3], 1.0, 1.0)
				elif MODEL == 'vgg16':
					model = AgenderNetVGG16()
				elif MODEL == 'inceptionv3':
					model = AgenderNetInceptionV3()
				elif MODEL == 'mobilenetv2':
					model = AgenderNetMobileNetV2()
				else :
					model = AgenderNetXception()
		trainDb = db[train_idx]
		trainPaths = paths[train_idx]
		trainAge = ageLabel[train_idx]
		trainGender = genderLabel[train_idx]
		
		testDb = db[test_idx]
		testPaths = paths[test_idx]
		testAge = ageLabel[test_idx]
		testGender = genderLabel[test_idx]

		losses = {
			"age_prediction": "categorical_crossentropy",
			"gender_prediction": "categorical_crossentropy",
		}
		metrics = {
			"age_prediction": mae,
			"gender_prediction": "acc",
		}
		
		if MODEL ==  'ssrnet' :
			del losses, metrics
			losses = {
				"age_prediction": "mae",
				"gender_prediction": "mae",
			}
			metrics = {
				"age_prediction": "mae",
				"gender_prediction":"binary_accuracy",
			}
		# print('[PHASE-1] Training ...')
		# callbacks = None
		# model.prepPhase1()
		# trainModel = model
		# if GPU > 1 :
		# 	trainModel = multi_gpu_model(model, gpus=GPU)
		# trainModel.compile(optimizer='adam', loss=losses, metrics=metrics)
		# hist = fitModel(model, 
		# 			trainDb, trainPaths, trainAge, trainGender, 
		# 			testDb, testPaths, testAge, testGender,
		# 			EPOCH, BATCH_SIZE, NUM_WORKER, 
		# 			callbacks, GPU)
		# with open(os.path.join('history', 'fold{}_p1.dict'.format(n_fold)), 'wb') as file_hist:
		# 	pickle.dump(hist.history, file_hist)
		
		print('[PHASE-2] Fine tuning ...')
		callbacks = [
			ModelCheckpoint("trainweight/model.{epoch:02d}-{val_loss:.4f}-{val_gender_prediction_acc:.4f}-{val_age_prediction_mae:.4f}.h5",
								 verbose=1,
								 save_best_only=True),
				# TYY_callbacks.DecayLearningRate([15])
			]
		
		if MODEL == 'ssrnet':
			del callbacks
			callbacks = [
				ModelCheckpoint("trainweight/model.{epoch:02d}-{val_loss:.4f}-{val_gender_prediction_binary_accuracy:.4f}-{val_age_prediction_mean_absolute_error:.4f}.h5",
									verbose=1,
									save_best_only=True),
				TYY_callbacks.DecayLearningRate([30, 60])
				]
		model.prepPhase2()
		trainModel = model
		if GPU > 1 :
			trainModel = multi_gpu_model(model, gpus=GPU)
		trainModel.compile(optimizer='adam', loss=losses, metrics=metrics)
		hist = fitModel(model, INPUT_SIZE, CATEGORICAL,
						trainDb, trainPaths, trainAge, trainGender, 
						testDb, testPaths, testAge, testGender, 
						EPOCH, BATCH_SIZE, NUM_WORKER, 
						callbacks, GPU)
		with open(os.path.join('history', 'fold{}_p2.dict'.format(n_fold)), 'wb') as file_hist:
			pickle.dump(hist.history, file_hist)

		n_fold += 1
		del trainDb, trainPaths, trainAge, trainGender 
		del	testDb, testPaths, testAge, testGender
		del	callbacks, model, trainModel


if __name__ == '__main__':
	main()