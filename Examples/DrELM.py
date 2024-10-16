import numpy as np
import pandas as pd
from keras.utils import to_categorical
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split, RepeatedKFold, cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn import preprocessing

from Layers.ELMLayer import ELMLayer
from Models.DrELMModel import DrELMModel

# Hyperparameters:
num_neurons = 500
depth = 3
alpha = 1000
n_splits = 10
n_repeats = 10

# Loading sample dataset from Data folder
path = "../Data/ionosphere.txt"
df = pd.read_csv(path, delimiter='\t').fillna(0)
X = df.values[:, 1:]
y = df.values[:, 0]

# Label encoding and features normalization
label_encoder = LabelEncoder()
y = label_encoder.fit_transform(y)  # Encode class labels to numerical values
X = preprocessing.normalize(X)  # Normalize feature vectors

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
y_train_cat = to_categorical(y_train)

# Create an instance of the Deep Representation ELM model (DrELMModel)
model = DrELMModel(activation='mish')

# Add layers to the Deep Representation ELM
model.add(ELMLayer(number_neurons=num_neurons, activation='identity'))
model.add(ELMLayer(number_neurons=num_neurons, activation='identity'))
model.add(ELMLayer(number_neurons=num_neurons, activation='identity'))
model.add(ELMLayer(number_neurons=num_neurons, activation='identity'))

# Define a cross-validation strategy
cv = RepeatedKFold(n_splits=n_splits, n_repeats=n_repeats)

# Perform cross-validation to evaluate the model performance
scores = cross_val_score(model, X, y, cv=cv, scoring='accuracy', error_score='raise')

# Print the mean accuracy score obtained from cross-validation
print(np.mean(scores))

# Fit the ELM model to the entire dataset
model.fit(X, y)

# Save the trained model to a file
model.save("Saved Models/DrELM_Model.h5")

# Load the saved model from the file
model = model.load("Saved Models/DrELM_Model.h5")

# Evaluate the accuracy of the model on the training data
acc = accuracy_score(model.predict(X), y)
print(acc)