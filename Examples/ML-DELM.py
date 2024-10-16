import numpy as np
import pandas as pd
from keras.utils import to_categorical
from sklearn.metrics import accuracy_score
from sklearn.model_selection import RepeatedKFold, cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn import preprocessing

from Layers.ELMLayer import ELMLayer
from Layers.KELMLayer import KELMLayer
from Models.ML_ELMModel import ML_ELMModel
from Resources.Kernel import CombinedProductKernel, Kernel

# Loading sample dataset from Data folder
file_path = "../Data/ionosphere.txt"
df = pd.read_csv(file_path, delimiter='\t').fillna(0)
X = df.values[:, 1:]
y = df.values[:, 0]

# Label encoding and features normalization
label_encoder = LabelEncoder()
y = label_encoder.fit_transform(y)  # Encode class labels to numerical values
X = preprocessing.normalize(X)  # Normalize feature vectors

# Initialize a Multilayer Extreme Learning Machine model
model = ML_ELMModel(verbose=0)

# Add D-ELM layers to the Multilayer Extreme Learning Machine with denoising mechanism
model.add(ELMLayer(number_neurons=50, denoising='sp', denoising_param=0.08))
model.add(ELMLayer(number_neurons=60, denoising='sp', denoising_param=0.08))
model.add(ELMLayer(number_neurons=50, denoising='sp', denoising_param=0.08))
model.add(ELMLayer(number_neurons=1000, denoising='sp', denoising_param=0.08))

# (option) Add D-KELM layers to the Multilayer Extreme Learning Machine with denoising mechanism
'''
model.add(KELMLayer(kernel=kernel))
model.add(KELMLayer(kernel=kernel))
model.add(KELMLayer(kernel=kernel))
model.add(ELMLayer(number_neurons=1000))
# model.fit(X, y_cat)
# pred = model.predict(X)
# print(accuracy_score(y, pred))
'''

# Define a cross-validation strategy
n_splits = 10
n_repeats = 10
cv = RepeatedKFold(n_splits=n_splits, n_repeats=n_repeats)

# Perform cross-validation to evaluate the model performance
scores = cross_val_score(model, X, y, cv=cv, scoring='accuracy', error_score='raise')

# Print the mean accuracy score obtained from cross-validation
print(np.mean(scores))

# Fit the DMLELM model to the entire dataset
model.fit(X, y)

# Save the trained model to a file
model.save('Saved Models/ML_DELM_Model.h5')

# Load the saved model from the file
model = model.load('Saved Models/ML_DELM_Model.h5')

# Evaluate the accuracy of the model on the training data
acc = accuracy_score(model.predict(X), y)
print(acc)
