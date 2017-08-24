import numpy as np
import tensorflow as tf
from tensorflow.contrib import slim

def weight(shape, name):
    initial = tf.truncated_normal(shape, mean=0.0, stddev=0.1, dtype=tf.float32)
    return tf.Variable(initial,name=name)

def conv2d(x, W):
    return tf.nn.conv2d(x, W, strides = [1,1,1,1], padding = 'VALID')

def deconv2d(x, W, output_shape, strides):
    return tf.nn.conv2d_transpose(x, W, output_shape = output_shape, strides = strides, padding = 'VALID')

def pool3d(x, ksize, strides, mode):
    x_pool = tf.transpose(x, perm=[0,3,1,2])
    x_pool = tf.expand_dims(x_pool, 4)
    if mode == 'avg':
        x_pool = tf.nn.avg_pool3d(x_pool, ksize, strides, 'VALID')
    if mode == 'max':
        x_pool = tf.nn.max_pool3d(x_pool, ksize, strides, 'VALID')
    x_pool = tf.squeeze(x_pool, [4])
    x_pool = tf.transpose(x_pool, perm=[0,2,3,1])
    return x_pool

def vgg_16(inputs,
           is_training=True,
           spatial_squeeze=True,
           variables_collections=None,
           scope='vgg_16'):
    """
    modification of vgg_16 in TF-slim
    see original code in https://github.com/tensorflow/models/blob/master/slim/nets/vgg.py
    """
    with tf.variable_scope(scope, 'vgg_16', [inputs]) as sc:
        end_points_collection = sc.name + '_end_points'
        # Collect outputs for conv2d, fully_connected and max_pool2d.
        with slim.arg_scope([slim.conv2d, slim.fully_connected, slim.max_pool2d],
                        outputs_collections=end_points_collection):
            net = slim.repeat(inputs, 2, slim.conv2d, 64, [3, 3], scope='conv1', biases_initializer=None,
                            activation_fn=None, variables_collections=variables_collections)
            net, argmax_1 = tf.nn.max_pool_with_argmax(net, [1,2,2,1], [1,2,2,1], padding='VALID', name='pool1')
            net = slim.repeat(net, 2, slim.conv2d, 128, [3, 3], scope='conv2', biases_initializer=None,
                            activation_fn=None, variables_collections=variables_collections)
            net, argmax_2 = tf.nn.max_pool_with_argmax(net, [1,2,2,1], [1,2,2,1], padding='VALID', name='pool2')
            net = slim.repeat(net, 3, slim.conv2d, 256, [3, 3], scope='conv3', biases_initializer=None,
                            activation_fn=None, variables_collections=variables_collections)
            net, argmax_3 = tf.nn.max_pool_with_argmax(net, [1,2,2,1], [1,2,2,1], padding='VALID', name='pool3')
            net = slim.repeat(net, 3, slim.conv2d, 512, [3, 3], scope='conv4', biases_initializer=None,
                            activation_fn=None, variables_collections=variables_collections)
            net, argmax_4 = tf.nn.max_pool_with_argmax(net, [1,2,2,1], [1,2,2,1], padding='VALID', name='pool4')
            net = slim.repeat(net, 3, slim.conv2d, 512, [3, 3], scope='conv5', biases_initializer=None,
                            activation_fn=None, variables_collections=variables_collections)
            net, argmax_5 = tf.nn.max_pool_with_argmax(net, [1,2,2,1], [1,2,2,1], padding='VALID', name='pool5')
            # Convert end_points_collection into a end_point dict.
            end_points = slim.utils.convert_collection_to_dict(end_points_collection)
            if spatial_squeeze:
                net = tf.squeeze(net, [1, 2], name='fc8/squeezed')
                end_points[sc.name + '/fc8'] = net
            # return argmax
            argmax = (argmax_1, argmax_2, argmax_3, argmax_4, argmax_5)
            return net, argmax, end_points

def unpool(pool, ind, shape, ksize=[1, 2, 2, 1], scope=None):
    with tf.name_scope(scope):
        input_shape =  tf.shape(pool)
        output_shape = [input_shape[0], input_shape[1] * ksize[1], input_shape[2] * ksize[2], input_shape[3]]
        flat_input_size = tf.cumprod(input_shape)[-1]
        flat_output_shape = tf.stack([output_shape[0], output_shape[1] * output_shape[2] * output_shape[3]])
        pool_ = tf.reshape(pool, tf.stack([flat_input_size]))
        batch_range = tf.reshape(tf.range(tf.cast(output_shape[0], tf.int64), dtype=ind.dtype),
                                shape=tf.stack([input_shape[0], 1, 1, 1]))
        b = tf.ones_like(ind) * batch_range
        b = tf.reshape(b, tf.stack([flat_input_size, 1]))
        ind_ = tf.reshape(ind, tf.stack([flat_input_size, 1]))
        ind_ = tf.concat([b, ind_], 1)
        ret = tf.scatter_nd(ind_, pool_, shape=tf.cast(flat_output_shape, tf.int64))
        ret = tf.reshape(ret, tf.stack(output_shape))
        ret = tf.reshape(ret, shape=shape)
        return ret

def read_tfrecord(tf_filename, image_size):
    filename_queue = tf.train.string_input_producer([tf_filename])
    reader = tf.TFRecordReader()
    __, serialized_example = reader.read(filename_queue)
    feature={ 'image_raw': tf.FixedLenFeature([], tf.string) }
    features = tf.parse_single_example(serialized_example, features=feature)
    image = tf.decode_raw(features['image_raw'], tf.uint8)
    image = tf.reshape(image, image_size)
    return image

def build_img_pair(img_batch):
    num = img_batch.shape[0]
    inputs = np.ones([img_batch.shape[0], img_batch.shape[1], img_batch.shape[2], 6], dtype = np.float32)
    outputs_gt = np.ones([img_batch.shape[0], img_batch.shape[1], img_batch.shape[2], 1], dtype = np.float32)
    for i in range(num):
        input_cast = img_batch[i,:,:,0:6].astype(dtype = np.float32)
        input_min = np.amin(input_cast)
        input_max = np.amax(input_cast)
        input_norm = (input_cast - input_min) / (input_max - input_min)
        gt = img_batch[i,:,:,6]
        gt_cast = gt.astype(dtype = np.float32)
        gt_min = np.amin(gt_cast)
        gt_max = np.amax(gt_cast)
        gt_norm = (gt_cast - gt_min) / (gt_max - gt_min)
        inputs[i,:,:,:] = input_norm
        outputs_gt[i,:,:,0] = gt_norm
    return inputs, outputs_gt