from Optimizers.ELMOptimizer import ELMOptimizer
from Resources.ActivationFunction import ActivationFunction
import tensorflow as tf

from Resources.generate_contrainted_weights import generate_contrainted_weights
from Resources.gram_schmidt import gram_schmidt
from Resources.ReceptiveFieldGenerator import ReceptiveFieldGenerator
from Resources.ReceptiveFieldGaussianGenerator import ReceptiveFieldGaussianGenerator


class ELMLayer:
    """
        Extreme Learning Machine Layer with various variants.

        This class represents a single hidden layer of an Extreme Learning Machine (ELM) model. It consists of a set of
        hidden neurons, each with its own activation function and input weights.

        Parameters:
        -----------
        number_neurons : int
            The number of neurons in the hidden layer.
        activation : str, default='tanh'
            The name of the activation function to be applied to the neurons that corresponds to the names of function
            in class Activation
        act_params : dict, default=None
            Additional parameters for the activation function (if needed - see implementation of particular function in
            class Activation).
        C : float, default=None
            Regularization parameter to control the degree of regularization applied to the hidden layer.
        beta_optimizer : ELMOptimizer, default=None
            An optimizer to optimize the output weights (beta) of the layer applied after the Moore-Penrose operation to
            finetune the beta parameter based on provided to optimizer loss function and optimization algorithm.
        is_orthogonalized : bool, default=False
            Indicates whether the input weights of the hidden neurons are orthogonalized, if yes the orthogonalization
            is performed (recommended to be applied for multilayer variants of ELM).
        receptive_field_generator : ReceptiveFieldGenerator, default=None
            An object for generating receptive fields to constrain the input weights of the hidden neurons.
        **params : dict
            Additional parameters to be passed to the layer.

        Attributes:
        -----------
        error_history : array-like, shape (n_iterations,)
            Array containing the error history during training (present only if ELMOptimizer is passed)
        feature_map : tensor, shape (n_samples, number_neurons)
            The feature map matrix generated by the layer.
        name : str, default="elm"
            The name of the layer.
        beta : tensor, shape (number_neurons, n_outputs) or None
            The output weights matrix of the layer.
        bias : tensor, shape (number_neurons,) or None
            The bias vector of the layer.
        alpha : tensor, shape (n_features, number_neurons) or None
            The input weights matrix of the layer.
        input : tensor or None
            The input data passed to the layer.
        output : tensor or None
            The output data computed by the layer.
        act_params : dict or None
            Additional parameters for the activation function.
        beta_optimizer : ELMOptimizer or None
            The optimizer used to optimize the output weights (beta) of the layer.
        is_orthogonalized : bool
            Indicates whether the input weights of the hidden neurons are orthogonalized.
        denoising : str or None
            The type of denoising applied to the layer passed as additional parameter to the constructor, it
            applies a given denoising algorithm to the input data to make classification more robust.
        denoising_param : float or None
            The parameter used for denoising.

        Example:
        -----------
        Initialize an Extreme Learning Machine (ELM) layer with 1000 neurons and mish activation function:

        >>> elm = ELMLayer(number_neurons=1000, activation='mish')

        Initialize an Extreme Learning Machine (ELM) layer with 1000 neurons and mish activation function and denoising
        mechanism activated that brings noise to the input data in order to make ELM more robust

        >>> elm = ELMLayer(number_neurons=1000, activation='mish', denoising=True)

        Initialize an Extreme Learning Machine (CELM) layer with 1000 neurons and constrained weights:

        >>> elm = ELMLayer(number_neurons=1000, activation='mish', constrained=True)

        Initialize an Extreme Learning Machine (RELM) layer with 1000 neurons and after the Moore-Penrose operation
        the ELMOptimizer - ISTAELMOptimizer optmizes the weights:
        Initialize optimizer (l1 norm)

        >>> optimizer = ISTAELMOptimizer(optimizer_loss='l1', optimizer_loss_reg=[0.01])

        Initialize a Regularized Extreme Learning Machine (RELM) layer with optimizer

        >>> elm = ELMLayer(number_neurons=100, activation='mish', beta_optimizer=optimizer)

        Initialize a Receptive Field Extreme Learning Machine (ELM) layer with Receptive Field Generator

        >>> rf = ReceptiveFieldGaussianGenerator(input_size=(28, 28, 1))

        # Initialize a Constrained Extreme Learning Machine layer with receptive field (RF-C-ELM)

        >>> elm = ELMLayer(number_neurons=1000, activation='mish', receptive_field_generator=rf, constrained=True)

        Create an ELM model using the trained ELM layer

        >>> model = ELMModel(elm)

        Define a cross-validation strategy

        >>> cv = RepeatedKFold(n_splits=10, n_repeats=50)

        Perform cross-validation to evaluate the model performance

        >>> scores = cross_val_score(model, X, y, cv=cv, scoring='accuracy', error_score='raise')

        Print the mean accuracy score obtained from cross-validation

        >>> print(np.mean(scores))
    """
    def __init__(self,
                 number_neurons,
                 activation='tanh',
                 act_params=None,
                 C=0.0,
                 beta_optimizer: ELMOptimizer = None,
                 is_orthogonalized=False,
                 receptive_field_generator=None,
                 **params):
        self.error_history = None
        self.feature_map = None
        self.name = "elm"
        self.beta = None
        self.bias = None
        self.alpha = None
        self.input = None
        self.output = None
        self.act_params = act_params
        self.beta_optimizer = beta_optimizer
        self.is_orthogonalized = is_orthogonalized
        if act_params is None:
            act = ActivationFunction(1.0)
        elif "act_param" in act_params and "act_param2" in act_params:
            act = ActivationFunction(act_param=act_params["act_param"], act_param2=act_params["act_param2"])
        elif "act_param" in act_params:
            act = ActivationFunction(act_param=act_params["act_param"])
        elif "knots" in act_params:
            act = ActivationFunction(knots=act_params["knots"])
        else:
            raise Exception("TypeError: Wrong specified activation function parameters")
        self.activation_name = activation
        self.activation = eval("act." + activation)
        self.number_neurons = number_neurons
        self.C = C
        self.receptive_field_generator = receptive_field_generator

        if "beta" in params:
            self.beta = params.pop("beta")
        if "alpha" in params:
            self.alpha = params.pop("alpha")
        if "bias" in params:
            self.bias = params.pop("bias")

        if "denoising" in params:
            self.denoising = params.pop("denoising")
        else:
            self.denoising = None
        if "denoising_param" in params:
            self.denoising_param = params.pop("denoising_param")
        else:
            self.denoising_param = None

        if 'constrained' in params and params['constrained'] is True:
            self.constrained = True
        else:
            self.constrained = False

        if 'rf_name' in params:
            rf = eval(f"{params['rf_name']}.load(params)")
            self.receptive_field_generator = rf

    def build(self, input_shape):
        """
        Builds the ELM layer by initializing weights and biases (obligatory before fitting the data).

        Parameters:
        -----------
        - input_shape (tuple): The shape of the input data.

        Returns:
        -----------
        None

        Example:
        -----------
            >>> elm = ELMLayer(number_neurons=1000, activation='mish')
            >>> elm.build(x.shape)
        """
        alpha = input_shape[-1]
        alpha_initializer = tf.random_uniform_initializer(-1, 1)
        self.alpha = tf.Variable(
            alpha_initializer(shape=(alpha, self.number_neurons)),
            dtype=tf.float32,
            trainable=False
        )
        bias_initializer = tf.random_uniform_initializer(0, 1)
        self.bias = tf.Variable(
            bias_initializer(shape=(self.number_neurons,)),
            dtype=tf.float32,
            trainable=False
        )
        if self.is_orthogonalized:
            self.alpha = gram_schmidt(self.alpha)
            self.bias = self.bias / tf.norm(self.bias)

    def fit(self, x, y):
        """
        Fits the Extreme Learning Machine model to the given training data.

        Parameters:
        -----------
            x (tf.Tensor): The input training data of shape (N, D), where N is the number of samples and D is the number of features.
            y (tf.Tensor): The target training data of shape (N, C), where C is the number of classes or regression targets.

        Returns:
        -----------
            None

        Fits the Extreme Learning Machine model to the given input-output pairs (x, y). This method generates the weights of the hidden layer neurons, calculates the feature map, and computes the output weights for the model.

        If constrained learning is enabled, the weights are generated considering the given output targets (y). If a receptive field generator is provided, it generates the receptive fields for the model's hidden neurons.

        After generating the feature map (H) using the input data (x) and hidden layer weights (alpha) along with the bias, the method applies the specified activation function to the feature map.
        :math:`H = f(x \\cdot \\alpha + bias)`

        If a regularization term (C) is provided, it is added to the diagonal of the feature map matrix.
        :math:`H = H + diag(C)`

        The output weights (beta) are computed using the Moore-Penrose pseudoinverse of the feature map matrix and the target output data (y). If a beta optimizer is specified, it further optimizes the output weights.
        :math:`H = H + diag(C)`

        The feature map (H) and the output (Beta) are stored as attributes of the model for later use.
        :math:`\\beta = H^{\\dagger} T`

        If a beta optimizer is provided, the method returns the optimized beta and the error history.

        Example:
        -----------
            >>> elm = ELMLayer(number_neurons=1000, activation='mish')
            >>> elm.build(x.shape)
            >>> elm.fit(train_data, train_targets)
        """
        x = tf.cast(x, dtype=tf.float32)
        y = tf.cast(y, dtype=tf.float32)
        self.input = x

        if self.constrained:
            generate_contrainted_weights(x, y, self.number_neurons)
        if self.receptive_field_generator is not None:
            self.receptive_field_generator.generate_receptive_fields(self.alpha)

        H = tf.matmul(x, self.alpha) + self.bias
        H = self.activation(H)

        if self.C is not None:
            H = tf.linalg.set_diag(H, tf.linalg.diag_part(H) + self.C)
        pH = tf.linalg.pinv(H)
        beta = tf.matmul(pH, y)
        self.beta = beta

        if self.beta_optimizer is not None:
            self.beta, self.error_history = self.beta_optimizer.optimize(beta, H, y)
        else:
            self.beta = beta

        self.feature_map = H
        self.output = tf.matmul(H, self.beta)

    def predict(self, x):
        """
        Predicts the output for the given input data.

        Parameters:
        -----------
        - x (tf.Tensor): Input data tensor.

        Returns:
        -----------
        tf.Tensor: Predicted output tensor.

        Example:
        -----------
            >>> elm = ELMLayer(number_neurons=1000, activation='mish')
            >>> elm.build(x.shape)
            >>> elm.fit(train_data, train_targets)
            >>> pred = elm.predict(test_data)
        """
        x = tf.cast(x, dtype=tf.float32)
        H = tf.matmul(x, self.alpha) + self.bias
        H = self.activation(H)
        output = tf.matmul(H, self.beta)
        return output

    def predict_proba(self, x):
        """
            Predicts the probabilities output for the given input data upon application of the softmax funtion.

            Parameters:
            -----------
            - x (tf.Tensor): Input data tensor.

            Returns:
            -----------
            tf.Tensor: Predicted output tensor.

            Example:
            -----------
            >>> elm = ELMLayer(number_neurons=1000, activation='mish')
            >>> elm.build(x.shape)
            >>> elm.fit(train_data, train_targets)
            >>> pred = elm.predict_proba(test_data)
        """
        x = tf.cast(x, dtype=tf.float32)
        pred = self.predict(x)
        return tf.keras.activations.softmax(pred)

    def calc_output(self, x):
        x = tf.cast(x, dtype=tf.float32)
        """
            Calculates the output of the ELM layer for the given input data.
    
            Parameters:
            -----------
            - x (tf.Tensor): Input data tensor.
    
            Returns:
            -----------
            tf.Tensor: Output tensor.
        """
        out = self.activation(tf.matmul(x, self.beta, transpose_b=True))
        self.output = out
        return out

    def apply_activation(self, x):
        """
            Applies activation function for the given input data.

            Parameters:
            -----------
            - x (tf.Tensor): Input data tensor.

            Returns:
            -----------
            tf.Tensor: Output tensor.
        """
        return self.activation(x)

    def __str__(self):
        """
            Returns a string representation of the ELM layer.

            Returns:
            -----------
            str: String representation.
        """
        return f"{self.name}, neurons: {self.number_neurons}"

    def count_params(self):
        """
            Counts the number of trainable and non-trainable parameters in the ELM layer.

            Returns:
            -----------
            dict: Dictionary containing counts for trainable, non-trainable, and total parameters.
        """
        if self.beta is None:
            trainable = 0
        else:
            trainable = self.beta.shape[0] * self.beta.shape[1]
        if self.alpha is None or self.bias is None:
            non_trainable = 0
        else:
            non_trainable = self.alpha.shape[0] * self.alpha.shape[1] + self.bias.shape[0]
        return {'trainable': trainable, 'non_trainable': non_trainable, 'all': trainable + non_trainable}

    def to_dict(self):
        """
            Convert the ELM layer attributes to a dictionary.

            Returns:
            -----------
                dict: A dictionary containing the attributes of the ELM layer.

            This method converts the attributes of the ELM layer to a dictionary format. It includes the following attributes:

            - 'name': The name of the ELM layer.
            - 'number_neurons': The number of neurons in the hidden layer.
            - 'activation': The activation function used in the hidden layer.
            - 'act_params': Additional parameters for the activation function.
            - 'C': The regularization term applied to the feature map matrix.
            - 'is_orthogonalized': A boolean indicating whether the hidden layer weights have been orthogonalized.
            - 'beta': The output weights of the ELM layer.
            - 'alpha': The hidden layer weights of the ELM layer.
            - 'bias': The bias terms of the ELM layer.
            - 'denoising': A boolean indicating whether denoising is applied to the input data.
            - 'denoising_param': Additional parameters for denoising.

            Only attributes with non-None values are included in the dictionary.
        """
        attributes = {
            'name': 'ELMLayer',
            'number_neurons': self.number_neurons,
            'activation': self.activation_name,
            'act_params': self.act_params,
            'C': self.C,
            'is_orthogonalized': self.is_orthogonalized,
            "beta": self.beta,
            "alpha": self.alpha,
            "bias": self.bias,
            "denoising": self.denoising,
            "denoising_param": self.denoising_param,
        }
        if self.receptive_field_generator is not None:
            attributes.update(self.receptive_field_generator.to_dict())
        filtered_attributes = {key: value for key, value in attributes.items() if value is not None}
        return filtered_attributes

    @classmethod
    def load(cls, attributes):
        """
            Load an ELM layer from a dictionary of attributes.

            Args:
            -----------
                attributes (dict): A dictionary containing the attributes of the ELM layer.

            Returns:
            -----------
                ELMLayer: An instance of the ELMLayer class initialized with the provided attributes.

            This class method creates an instance of the ELMLayer class using the attributes provided in the input dictionary.
            The dictionary should include the following attributes:

            - 'name': The name of the ELM layer.
            - 'number_neurons': The number of neurons in the hidden layer.
            - 'activation': The activation function used in the hidden layer.
            - 'act_params': Additional parameters for the activation function.
            - 'C': The regularization term applied to the feature map matrix.
            - 'is_orthogonalized': A boolean indicating whether the hidden layer weights have been orthogonalized.
            - 'beta': The output weights of the ELM layer.
            - 'alpha': The hidden layer weights of the ELM layer.
            - 'bias': The bias terms of the ELM layer.
            - 'denoising': A boolean indicating whether denoising is applied to the input data.
            - 'denoising_param': Additional parameters for denoising.

            Example:
            -----------
                >>> elm_layer = ELMLayer.load(attributes)

        """
        return cls(attributes)
