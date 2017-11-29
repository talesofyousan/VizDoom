# modified https://github.com/icoxfog417/chainer_pong/blob/master/model/dqn_agent.py
import os
import numpy as np
from chainer import Chain
from chainer import Variable
from chainer import cuda
from chainer import serializers
import chainer.functions as F
import chainer.links as L
from chaintestmodel5.agent import Agent
import chainer.initializers as I 

from skimage.color import rgb2gray
from skimage.transform import resize

class Q(Chain):
    """
    You want to optimize this function to determine the action from state (state is represented by CNN vector)
    """

    sizex = 80  # 80 X y image
    sizey = 80  # x X 80 image
    
    def __init__(self, n_history, n_action, on_gpu=False):
        self.n_history = n_history
        self.n_action = n_action
        self.on_gpu = on_gpu
        super(Q, self).__init__(
            l1=L.Convolution2D(n_history, 32, ksize=8, stride=4, nobias=False, initialW=I.HeNormal(np.sqrt(2) / np.sqrt(2))),
            l2=L.Convolution2D(32, 64, ksize=3, stride=2, nobias=False, initialW=I.HeNormal(np.sqrt(2) / np.sqrt(2))),
            l3=L.Convolution2D(64, 64, ksize=3, stride=1, nobias=False, initialW=I.HeNormal(np.sqrt(2)/ np.sqrt(2))),
            l4=L.Linear(3136, 512, initialW=I.HeNormal(np.sqrt(2)/ np.sqrt(2))),
            out=L.Linear(512, self.n_action, initialW=np.zeros((n_action, 512), dtype=np.float32))
        )
        if on_gpu:
            self.to_gpu()
    
    def __call__(self, state: np.ndarray):
        _state = self.arr_to_gpu(state)
        s = Variable(_state)
        h1 = F.relu(self.l1(s))
        h2 = F.relu(self.l2(h1))
        h3 = F.relu(self.l3(h2))
        h4 = F.relu(self.l4(h3))
        q_value = self.out(h4)
        return q_value
    
    def arr_to_gpu(self, arr):
        return arr if not self.on_gpu else cuda.to_gpu(arr)


class DQNAgent(Agent):
    
    def __init__(self, actions, epsilon=1, n_history=4, on_gpu=False, model_path="", load_if_exist=True):
        self.actions = actions
        self.epsilon = epsilon
        self.q = Q(n_history, len(actions), on_gpu)
        self._state = []
        self._observations = [
            np.zeros((self.q.sizex, self.q.sizey), np.float32), 
            np.zeros((self.q.sizex, self.q.sizey), np.float32)
        ]  # now & pre
        self.last_action = 0
        self.model_path = model_path if model_path else os.path.join(os.path.dirname(__file__), "./store")
        if not os.path.exists(self.model_path):
            print("make directory to store model at {0}".format(self.model_path))
            os.mkdir(self.model_path)
        else:
            models = self.get_model_files()
            if load_if_exist and len(models) > 0:
                print("load model file {0}.".format(models[-1]))
                serializers.load_npz(os.path.join(self.model_path, models[-1]), self.q)  # use latest model
    
    def _update_state(self, observation):
        formatted = self._format(observation)
        state = np.maximum(formatted, self._observations[0])#[0]  ___ operands could not be broadcast together with shapes (0,40) (80,80) ____
        self._state.append(state)
        if len(self._state) > self.q.n_history:
            self._state.pop(0)
        return formatted
    
    @classmethod
    def _format(cls, image):
        """ prepro 210x160x3 uint8 frame into 6400 (80x80) 1D float vector """
        im = resize(rgb2gray(image), (80, 80))
        return im.astype(np.float32)

    def start(self, observation):
        self._state = []
        self._observations = [
            np.zeros((self.q.sizex, self.q.sizey), np.float32), 
            np.zeros((self.q.sizex, self.q.sizey), np.float32)
        ]
        self.last_action = 0

        action = self.act(observation, 0)
        return action
    
    def act(self, observation, reward):
        o = self._update_state(observation)
        s = self.get_state()
        qv = self.q(np.array([s])) # batch size = 1

        if np.random.rand() < self.epsilon:
            action = np.random.randint(0, len(self.actions))
        else:
            action = np.argmax(qv.data[-1])
        
        self._observations[-1] = self._observations[0].copy()
        self._observations[0] = o
        self.last_action = action

        return action

    def get_state(self):
        state = []
        for  i in range(self.q.n_history):
            if i < len(self._state):
                state.append(self._state[i])
            else:
                state.append(np.zeros((self.q.sizex, self.q.sizey), dtype=np.float32))
        
        np_state = np.array(state)  # n_history x (width x height)
        return np_state
    
    #TODO : change file names to doom names
    def save(self, index=0):
        fname = "pong.model" if index == 0 else "pong_{0}.model".format(index)
        path = os.path.join(self.model_path, fname)
        serializers.save_npz(path, self.q)
    
    def get_model_files(self):
        files = os.listdir(self.model_path)
        model_files = []
        for f in files:
            if f.startswith("pong") and f.endswith(".model"):
                model_files.append(f)
        
        model_files.sort()
        return model_files