# -*- coding: utf-8 -*-
"""Yet another copy of Yet another copy of ganstyletransfer.ipynb

Automatically generated by Colab.

"""

from google.colab import drive
drive.mount('/content/drive')

pip install git+https://github.com/tensorflow/examples.git

import tensorflow as tf
import os
import time
import matplotlib.pyplot as plt
from IPython.display import clear_output
import tensorflow_datasets as tfds
from tensorflow_examples.models.pix2pix import pix2pix
from keras.layers import Conv2D, LeakyReLU, Activation, Concatenate, BatchNormalization, GroupNormalization, ReLU, Conv2DTranspose
from keras.models import Model
from keras import Input
AUTOTUNE = tf.data.AUTOTUNE

!pip install -q kaggle

from google.colab import files
files.upload()
!mkdir -p ~/.kaggle
!cp kaggletoken.json ~/.kaggle/

#!kaggle datasets download -d cyanex1702/cyberverse-mini
#!kaggle datasets download -d residentmario/segmented-bob-ross-images
!kaggle datasets download -d myzhang1029/chinese-landscape-painting-dataset

!unzip -q chinese-landscape-painting-dataset.zip

from tensorflow.io import decode_jpeg, read_file
from tensorflow.data import Dataset
directory_path = '/content'
cyberpunk = Dataset.list_files(directory_path + '/*.jpg', shuffle=True)

!ls /content/train/images | wc -l

current_application = 'ukiyoe1_paper_model'
artist = "ukiyoe"

monet_train = cyberpunk.take(2000)
monet_test = cyberpunk.skip(2000)

dataset, metadata = tfds.load(f'cycle_gan/{artist}2photo',
                              with_info=True, as_supervised=True)
#monet_train = dataset['trainA']
photo_train = dataset['trainB']
#monet_test = dataset['testA']
photo_test = dataset['testB']

BUFFER_SIZE = 1000
BATCH_SIZE = 4
IMG_WIDTH = 256
IMG_HEIGHT = 256

def kaggle_preprocess(file_path):
  img = read_file(file_path)
  img = tf.io.decode_jpeg(img, channels = 3)
  img = tf.image.resize(img, [256, 256])
  return img
def crop_random(image):
  cropped = tf.image.random_crop(
      image, size=[IMG_HEIGHT, IMG_WIDTH, 3])

  return cropped

def normalize(image, label): #normalizes to [-1, 1]
  image = tf.cast(image, tf.float32)
  image = (image / 127.5) - 1
  return image
def normalize_kaggle(image): #normalizes to [-1, 1]
  image = kaggle_preprocess(image)
  image = tf.cast(image, tf.float32)
  image = (image / 127.5) - 1
  return image
def random_jit(image):
  image = tf.image.resize(image, [286, 286],
                          method=tf.image.ResizeMethod.NEAREST_NEIGHBOR)
  image = crop_random(image)
  image = tf.image.random_flip_left_right(image)
  return image

def preprocess_image(image, label):
  image = random_jit(image)
  image = normalize(image, label)
  return image
def preprocess_image_kaggle(image_path):
  image = kaggle_preprocess(image_path)
  image = random_jit(image)
  image = normalize(image, "")
  return image

'''
monet_train = monet_train.cache().map(
    preprocess_image_kaggle, num_parallel_calls=AUTOTUNE).shuffle(
        BUFFER_SIZE).batch(BATCH_SIZE)
photo_train = photo_train.cache().map(
    preprocess_image, num_parallel_calls=AUTOTUNE).shuffle(
        BUFFER_SIZE).batch(BATCH_SIZE)

monet_test = monet_test.map(
    normalize_kaggle, num_parallel_calls=AUTOTUNE).cache().shuffle(
        BUFFER_SIZE).batch(BATCH_SIZE)
'''
photo_test = photo_test.map(
    normalize, num_parallel_calls=AUTOTUNE).cache().batch(BATCH_SIZE)

sample_monet_train = next(iter(monet_train))
sample_photo = next(iter(photo_train))
plt.subplot(121)
plt.title(artist)
plt.imshow(sample_monet_train[0] * 0.5 + 0.5)

plt.subplot(122)
plt.title('Photo')
plt.imshow(sample_photo[0] * 0.5 + 0.5)

class InstanceNormalization(tf.keras.layers.Layer):

  def __init__(self):
    super(InstanceNormalization, self).__init__()
    self.epsilon = 1e-5

  def build(self, input_shape):
    self.scale = self.add_weight(
        name='scale',
        shape=input_shape[-1:],
        initializer=tf.random_normal_initializer(1., 0.02),
        trainable=True)

    self.off = self.add_weight(
        name='offset',
        shape=input_shape[-1:],
        initializer='zeros',
        trainable=True)

  def call(self, x):
    res = tf.nn.moments(x, axes=[1, 2], keepdims=True)
    avg = res[0]
    var = res[1]
    normalized = (x - avg) * tf.math.rsqrt(var + self.epsilon)
    return self.scale * normalized + self.off

#generator given as UNET in Pix2Pix
def unet_generator():
  inputs = tf.keras.layers.Input(shape = [256, 256, 3])
  init = tf.random_normal_initializer(0., 0.02)
  down_sample = [
      tf.keras.Sequential([
          tf.keras.layers.Conv2D(64, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02), use_bias=False),
          tf.keras.layers.LeakyReLU()
      ]),
      tf.keras.Sequential([
          tf.keras.layers.Conv2D(128, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02), use_bias=False),
          InstanceNormalization(),
          tf.keras.layers.LeakyReLU()
      ]),
      tf.keras.Sequential([
          tf.keras.layers.Conv2D(256, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02), use_bias=False),
          InstanceNormalization(),
          tf.keras.layers.LeakyReLU()
      ]),
      tf.keras.Sequential([
          tf.keras.layers.Conv2D(512, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02), use_bias=False),
          InstanceNormalization(),
          tf.keras.layers.LeakyReLU()
      ]),
      tf.keras.Sequential([
          tf.keras.layers.Conv2D(512, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02), use_bias=False),
          InstanceNormalization(),
          tf.keras.layers.LeakyReLU()
      ]),
      tf.keras.Sequential([
          tf.keras.layers.Conv2D(512, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02), use_bias=False),
          InstanceNormalization(),
          tf.keras.layers.LeakyReLU()
      ]),
      tf.keras.Sequential([
          tf.keras.layers.Conv2D(512, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02), use_bias=False),
          InstanceNormalization(),
          tf.keras.layers.LeakyReLU()
      ]),tf.keras.Sequential([
          tf.keras.layers.Conv2D(512, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02), use_bias=False),
          InstanceNormalization(),
          tf.keras.layers.LeakyReLU()
      ]),
  ]

  up_sample = [
      tf.keras.Sequential([
          tf.keras.layers.Conv2DTranspose(512, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02)),
          InstanceNormalization(),
          tf.keras.layers.Dropout(0.5),
          tf.keras.layers.ReLU()
      ]),
      tf.keras.Sequential([
          tf.keras.layers.Conv2DTranspose(512, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02)),
          InstanceNormalization(),
          tf.keras.layers.Dropout(0.5),
          tf.keras.layers.ReLU()
      ]),
      tf.keras.Sequential([
          tf.keras.layers.Conv2DTranspose(512, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02)),
          InstanceNormalization(),
          tf.keras.layers.Dropout(0.5),
          tf.keras.layers.ReLU()
      ]),
      tf.keras.Sequential([
          tf.keras.layers.Conv2DTranspose(512, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02)),
          InstanceNormalization(),
          tf.keras.layers.ReLU()
      ]),
      tf.keras.Sequential([
          tf.keras.layers.Conv2DTranspose(256, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02)),
          InstanceNormalization(),
          tf.keras.layers.ReLU()
      ]),
      tf.keras.Sequential([
          tf.keras.layers.Conv2DTranspose(128, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02)),
          InstanceNormalization(),
          tf.keras.layers.ReLU()
      ]),
      tf.keras.Sequential([
          tf.keras.layers.Conv2DTranspose(64, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02)),
          InstanceNormalization(),
          tf.keras.layers.ReLU()
      ]),
  ]
  final = tf.keras.layers.Conv2DTranspose(3, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02), activation = 'tanh')
  x = inputs
  skips = []
  for down_layer in down_sample:
    x = down_layer(x)
    skips.append(x)
  skips = reversed(skips[:-1])
  for up_layer, skip in zip(up_sample, skips):
    x = up_layer(x)
    x = tf.keras.layers.Concatenate()([x, skip])

  x = final(x)
  return tf.keras.Model(inputs=inputs, outputs=x)

def resnet_block(filters, input_layer):
  initializer = tf.random_normal_initializer(0., 0.02)
  padded = tf.pad(input_layer, [[0,0], [1, 1], [1, 1] , [0, 0]], mode="REFLECT")
  x = Conv2D(filters, (3, 3), padding='VALID', kernel_initializer = initializer)(padded)
  x = InstanceNormalization()(x)
  x = ReLU()(x)
  x = tf.pad(x, [[0,0], [1, 1], [1, 1] , [0, 0]], mode="REFLECT")
  x = Conv2D(filters, (3, 3), padding='VALID', kernel_initializer = initializer)(x)
  x = InstanceNormalization()(x)
  return ReLU()(x + input_layer)
  '''
  x = Conv2D(filters, (3, 3), padding='same', kernel_initializer=initializer)(input_layer)
  x = InstanceNormalization()(x)
  x = ReLU()(x)
  x = Conv2D(filters, (3, 3), padding='same', kernel_initializer=initializer)(x)
  x = InstanceNormalization()(x)
  x = Concatenate()([x, input_layer])
  '''
  return x

#generator given as UNET in Pix2Pix
def unet_generator():
  inputs = tf.keras.layers.Input(shape = [256, 256, 3])
  init = tf.random_normal_initializer(0., 0.02)
  down_sample = [
      tf.keras.Sequential([
          tf.keras.layers.Conv2D(64, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02), use_bias=False),
          tf.keras.layers.LeakyReLU()
      ]),
      tf.keras.Sequential([
          tf.keras.layers.Conv2D(128, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02), use_bias=False),
          InstanceNormalization(),
          tf.keras.layers.LeakyReLU()
      ]),
      tf.keras.Sequential([
          tf.keras.layers.Conv2D(256, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02), use_bias=False),
          InstanceNormalization(),
          tf.keras.layers.LeakyReLU()
      ]),
      tf.keras.Sequential([
          tf.keras.layers.Conv2D(512, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02), use_bias=False),
          InstanceNormalization(),
          tf.keras.layers.LeakyReLU()
      ]),
      tf.keras.Sequential([
          tf.keras.layers.Conv2D(512, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02), use_bias=False),
          InstanceNormalization(),
          tf.keras.layers.LeakyReLU()
      ]),
      tf.keras.Sequential([
          tf.keras.layers.Conv2D(512, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02), use_bias=False),
          InstanceNormalization(),
          tf.keras.layers.LeakyReLU()
      ]),
      tf.keras.Sequential([
          tf.keras.layers.Conv2D(512, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02), use_bias=False),
          InstanceNormalization(),
          tf.keras.layers.LeakyReLU()
      ]),tf.keras.Sequential([
          tf.keras.layers.Conv2D(512, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02), use_bias=False),
          InstanceNormalization(),
          tf.keras.layers.LeakyReLU()
      ]),
  ]

  up_sample = [
      tf.keras.Sequential([
          tf.keras.layers.Conv2DTranspose(512, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02)),
          InstanceNormalization(),
          tf.keras.layers.Dropout(0.5),
          tf.keras.layers.ReLU()
      ]),
      tf.keras.Sequential([
          tf.keras.layers.Conv2DTranspose(512, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02)),
          InstanceNormalization(),
          tf.keras.layers.Dropout(0.5),
          tf.keras.layers.ReLU()
      ]),
      tf.keras.Sequential([
          tf.keras.layers.Conv2DTranspose(512, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02)),
          InstanceNormalization(),
          tf.keras.layers.Dropout(0.5),
          tf.keras.layers.ReLU()
      ]),
      tf.keras.Sequential([
          tf.keras.layers.Conv2DTranspose(512, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02)),
          InstanceNormalization(),
          tf.keras.layers.ReLU()
      ]),
      tf.keras.Sequential([
          tf.keras.layers.Conv2DTranspose(256, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02)),
          InstanceNormalization(),
          tf.keras.layers.ReLU()
      ]),
      tf.keras.Sequential([
          tf.keras.layers.Conv2DTranspose(128, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02)),
          InstanceNormalization(),
          tf.keras.layers.ReLU()
      ]),
      tf.keras.Sequential([
          tf.keras.layers.Conv2DTranspose(64, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02)),
          InstanceNormalization(),
          tf.keras.layers.ReLU()
      ]),
  ]
  final = tf.keras.layers.Conv2DTranspose(3, 4, strides=2, padding='same', kernel_initializer = tf.random_normal_initializer(0., 0.02), activation = 'tanh')
  x = inputs
  skips = []
  for down_layer in down_sample:
    x = down_layer(x)
    skips.append(x)
  skips = reversed(skips[:-1])
  for up_layer, skip in zip(up_sample, skips):
    x = up_layer(x)
    x = tf.keras.layers.Concatenate()([x, skip])

  x = final(x)
  return tf.keras.Model(inputs=inputs, outputs=x)

def resnet_generator(resnet_blocks=9):
  initializer = tf.random_normal_initializer(0., 0.02)
  inp = Input(shape=(256, 256, 3))
  x = tf.pad(inp, [[0, 0], [3, 3], [3, 3], [0, 0]], mode='REFLECT')
  '''
  x = Conv2D(32, (7, 7), padding='same', kernel_initializer=initializer)(padded)
  x = InstanceNormalization()(x)
  x = ReLU()(x)
  x = Conv2D(64, (3, 3), padding='same', kernel_initializer=initializer)(inp)
  x = InstanceNormalization()(x)
  x = ReLU()(x)
  x = Conv2D(128, (3, 3), padding='same', kernel_initializer=initializer)(inp)
  x = InstanceNormalization()(x)
  x = ReLU()(x)
  for _ in range(resnet_blocks):
    x = resnet_block(128, x)
  x = Conv2DTranspose(64, (3, 3), strides = (2, 2), padding = 'same', kernel_initializer=initializer)(x)
  x = InstanceNormalization()(x)
  x = ReLU()(x)
  x = Conv2DTranspose(32, (3, 3), strides = (2, 2), padding = 'same', kernel_initializer=initializer)(x)
  x = InstanceNormalization()(x)
  x = ReLU()(x)
  x = Conv2D(3, (7, 7), padding = 'same')(x)
  x = InstanceNormalization()(x)
  out = Activation('tanh')(x)
  model = Model(inp, out)
  '''
  x = Conv2D(64, (7, 7), padding='valid', kernel_initializer=initializer)(x)
  x = InstanceNormalization()(x)
  x = ReLU()(x)
  x = Conv2D(128, (3, 3), strides = (2, 2), padding='same', kernel_initializer=initializer)(x)
  x = InstanceNormalization()(x)
  x = ReLU()(x)
  x = Conv2D(256, (3, 3), strides = (2, 2), padding='same', kernel_initializer=initializer)(x)
  x = InstanceNormalization()(x)
  x = ReLU()(x)
  for _ in range(resnet_blocks):
    x = resnet_block(256, x)
  x = Conv2DTranspose(128, (3, 3), strides = (2, 2), padding = 'same', kernel_initializer=initializer)(x)
  x = InstanceNormalization()(x)
  x = ReLU()(x)
  x = Conv2DTranspose(64, (3, 3), strides = (2, 2), padding = 'same', kernel_initializer=initializer)(x)
  x = InstanceNormalization()(x)
  x = ReLU()(x)
  x = Conv2DTranspose(3, (7, 7), padding = 'same', kernel_initializer=initializer)(x)
  x = InstanceNormalization()(x)
  out = Activation('tanh')(x)
  model = Model(inp, out)
  return model

def patchgan_discriminator():
  init = tf.random_normal_initializer(0., 0.02)
  inp = Input(shape=(256, 256, 3))
  x = Conv2D(64, (4,4), strides=(2,2), padding='same', kernel_initializer=init)(inp)
  x = LeakyReLU(alpha=0.2)(x)
  x = Conv2D(128, (4,4), strides=(2,2), padding='same', kernel_initializer=init)(x)
  x = InstanceNormalization()(x)
  x = LeakyReLU(alpha=0.2)(x)
  x = Conv2D(256, (4,4), strides=(2,2), padding='same', kernel_initializer=init)(x)
  x = InstanceNormalization()(x)
  x = LeakyReLU(alpha=0.2)(x)
  x = Conv2D(512, (4,4), strides=1, kernel_initializer=init)(x)
  x = InstanceNormalization()(x)
  x = LeakyReLU(alpha=0.2)(x)
  out = Conv2D(1, (4,4), padding='same', kernel_initializer=init)(x)
  return Model(inp, out)

#make generator and discriminators
OUTPUT_CHANNELS = 3

#generator_g = pix2pix.unet_generator(norm_type='instancenorm', output_channels=3)
#generator_f = pix2pix.unet_generator(norm_type='instancenorm', output_channels=3)
generator_g = unet_generator()
generator_f = unet_generator()

#discriminator_x = pix2pix.discriminator(norm_type='instancenorm', target=False)
#discriminator_y = pix2pix.discriminator(norm_type='instancenorm', target=False)
discriminator_x = patchgan_discriminator()
discriminator_y = patchgan_discriminator()

LAMBDA = 10

bce_loss = tf.keras.losses.BinaryCrossentropy(from_logits=True)
#LOSS FUNCTIONS
def discriminator_loss(real, generated):
  real_loss = bce_loss(tf.ones_like(real), real)

  gen_loss = bce_loss(tf.zeros_like(generated),  generated)

  return real_loss + gen_loss * 0.5
def generator_loss(generated):
  return bce_loss(tf.ones_like(generated), generated)
  #return tf.reduce_mean(tf.math.squared_difference(generated, 1))

def cycle_loss(real, cycled):
  return LAMBDA * tf.reduce_mean(tf.abs(real - cycled))
def id_loss(real, same):
  return LAMBDA * 0.5 * tf.reduce_mean(tf.abs(real - same))

generator_g_optimizer = tf.keras.optimizers.Adam(2e-4, beta_1=0.5)
generator_f_optimizer = tf.keras.optimizers.Adam(2e-4, beta_1=0.5)

discriminator_x_optimizer = tf.keras.optimizers.Adam(2e-4, beta_1=0.5)
discriminator_y_optimizer = tf.keras.optimizers.Adam(2e-4, beta_1=0.5)

#for switching to pixpix

resnets = ["monet9_paper_model", "bob_ross_paper_model2", "cezanne_paper_model", "vangogh1_paper_model", "ukiyoe1_paper_model"]
pixpix = ["chinese_model1_pixpix", "monet_model_100_epochs"]

models = []
for model in resnets:
  current_application = model
  artist = model
  checkpoint_path = f"/content/drive/MyDrive/train/{current_application}"
  g = resnet_generator()
  ckpt = tf.train.Checkpoint(generator_f= g)
  ckpt_manager = tf.train.CheckpointManager(ckpt, checkpoint_path, max_to_keep=5)
  if ckpt_manager.latest_checkpoint:
    ckpt.restore(ckpt_manager.latest_checkpoint)
    print ('Latest checkpoint restored!!')
  models.append(g)
for model in pixpix:
  current_application = model
  artist = model
  checkpoint_path = f"/content/drive/MyDrive/train/{current_application}"
  g = unet_generator()
  ckpt = tf.train.Checkpoint(generator_f= g)
  ckpt_manager = tf.train.CheckpointManager(ckpt, checkpoint_path, max_to_keep=5)
  if ckpt_manager.latest_checkpoint:
    ckpt.restore(ckpt_manager.latest_checkpoint)
    print ('Latest checkpoint restored!!')
  models.append(g)

for inp in photo_test.take(20):
  for model, title in zip(models, resnets + pixpix):
    generate_images(model, inp, title)

EPOCHS = 100

def generate_images(model, test_input, title):
  prediction = model(test_input)

  plt.figure(figsize=(12, 12))

  display_list = [test_input[0], prediction[0]]
  title = ['Photo', f'{title} style']

  for i in range(2):
    plt.subplot(1, 2, i+1)
    plt.title(title[i])
    # getting the pixel values between [0, 1] to plot it.
    plt.imshow(display_list[i] * 0.5 + 0.5)
    plt.axis('off')
  plt.show()
'''
def generate_images(models, test_input, model_strs):
  predictions = [model(test_input) for model in models]

  plt.figure(figsize=(12, 12))

  display_list = [test_input[0]] +  [prediction[0] for prediction in predictions]
  title = ['Photo'] + model_strs

  for i in range(len(title)):
    plt.subplot(1, len(title), i+1)
    plt.title(title[i])
    # getting the pixel values between [0, 1] to plot it.
    plt.imshow(display_list[i] * 0.5 + 0.5)
    plt.axis('off')
  plt.show()
'''

@tf.function
def train_step(x_domain, y_domain):
  with tf.GradientTape(persistent=True) as tape:
    f_y = generator_g(x_domain, training=True)
    cyc_x = generator_f(f_y, training=True)

    f_x = generator_f(y_domain, training=True)
    cycled_y = generator_g(f_x, training=True)

    #identity loss
    same_x = generator_f(x_domain, training=True)
    same_y = generator_g(y_domain, training=True)

    disc_x_domain = discriminator_x(x_domain, training=True)
    disc_y_domain = discriminator_y(y_domain, training=True)

    disc_f_x = discriminator_x(f_x, training=True)
    disc_f_y = discriminator_y(f_y, training=True)

    #generator loss from discriminator
    gen_g_loss = generator_loss(disc_f_y)
    gen_f_loss = generator_loss(disc_f_x)

    #cycle loss
    total_cycle_loss = cycle_loss(x_domain, cyc_x) + cycle_loss(y_domain, cycled_y)

    #total generator loss
    total_gen_g_loss = gen_g_loss + total_cycle_loss + id_loss(y_domain, same_y)
    total_gen_f_loss = gen_f_loss + total_cycle_loss + id_loss(x_domain, same_x)

    disc_x_loss = discriminator_loss(disc_x_domain, disc_f_x)
    disc_y_loss = discriminator_loss(disc_y_domain, disc_f_y)

  # gradients
  generator_g_gradients = tape.gradient(total_gen_g_loss,
                                        generator_g.trainable_variables)
  generator_f_gradients = tape.gradient(total_gen_f_loss,
                                        generator_f.trainable_variables)

  discriminator_x_gradients = tape.gradient(disc_x_loss,
                                            discriminator_x.trainable_variables)
  discriminator_y_gradients = tape.gradient(disc_y_loss,
                                            discriminator_y.trainable_variables)
  generator_g_optimizer.apply_gradients(zip(generator_g_gradients,
                                            generator_g.trainable_variables))

  generator_f_optimizer.apply_gradients(zip(generator_f_gradients,
                                            generator_f.trainable_variables))

  discriminator_x_optimizer.apply_gradients(zip(discriminator_x_gradients,
                                                discriminator_x.trainable_variables))
 
  discriminator_y_optimizer.apply_gradients(zip(discriminator_y_gradients,
                                                discriminator_y.trainable_variables))

for epoch in range(EPOCHS):

  n = 0
  for image_x, image_y in tf.data.Dataset.zip((monet_train, photo_train)):
    train_step(image_x, image_y)

  if epoch % 5 == 0:
    for inp in photo_test.take(3):
      generate_images(generator_f, inp)

  ckpt_save_path = ckpt_manager.save()

for inp in photo_test.take(40):
  generate_images(generator_f, inp)

for inp in photo_test.take(40):
  generate_images(generator_f, inp)

for inp in photo_test.take(40):
  generate_images(generator_f, inp)

for inp in photo_test.take(40):
  generate_images(generator_f, inp)

for inp in photo_test.take(40):
  generate_images(generator_f, inp)

for inp in photo_test.take(40):
  generate_images(generator_f, inp)

for inp in photo_test.take(40):
  generate_images(generator_f, inp)

