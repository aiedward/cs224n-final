import tensorflow as tf
import numpy as np

PAD_ID = 0
SOS_ID = 1
UNK_ID = 2 

class Config(object):
	"""Holds model hyperparams and data information.

    The config class is used to store various hyperparameters and dataset
    information parameters. Model objects are passed a Config() object at
    instantiation.

    CHECK WHICH VALUES WE ACTUALLY NEED AND MODIFY THEM
    """
	n_features = 36
	n_classes = 3
	dropout = 0.5
	embed_size = 50
	encoder_hidden_size = 200
	decoder_hidden_size = encoder_hidden_size * 2
	batch_size = 3 #batch size was previously 2048
	n_epochs = 10
	lr = 0.001
	max_sentence_len = 20
	vocab_size = 1000

class RNN(object):
	def __init__(self, config):
		self.config = config
		loaded = np.load('data/summarization/glove.trimmed.50.npz'.format(self.config.embed_size))
		self.embedding_matrix = loaded['glove']

	def add_placeholders(self):
		self.encoder_inputs_placeholder = tf.placeholder(tf.int32, shape=([None, self.config.max_sentence_len, 1]), name="x")
		self.labels_placeholder = tf.placeholder(tf.int32, shape=([None, self.config.max_sentence_len, 1]), name="y")
		# still not sure that we need the 1's above
		self.mask_placeholder = tf.placeholder(tf.bool, shape=([None, self.config.max_sentence_len]))
		#SWITHCED TYPE OF THE PLACEHOLDERS FROM FLOAT TO INT

	def create_feed_dict(self, inputs_batch, labels_batch=None, mask_batch=None):
		feed_dict = {
			self.inputs_placeholder: inputs_batch,
		}
		if labels_batch is not None:
			feed_dict[self.labels_placeholder] = labels_batch

		if mask_batch is not None: # TODO: create mask_batch using ground truth
			feed_dict[self.mask_placeholder] = mask_batch
		return feed_dict


	def add_embedding(self):
	   	"""Adds an embedding layer that maps from input tokens (integers) to vectors and then
	    concatenates those vectors:

            - Create an embedding tensor and initialize it with self.pretrained_embeddings.
            - Use the input_placeholder to index into the embeddings tensor, resulting in a
              tensor of shape (None, max_length, n_features, embed_size).
            - Concatenates the embeddings by reshaping the embeddings tensor to shape
              (None, max_length, n_features * embed_size).

        Returns:
            embeddings: tf.Tensor of shape (None, max_length, embed_size)
        """
		### YOUR CODE HERE (~4-6 lines)
		embedding_tensor = tf.Variable(self.embedding_matrix)
		lookup_tensor = tf.nn.embedding_lookup(embedding_tensor, self.inputs_placeholder)
		embeddings = tf.reshape(lookup_tensor, [-1, self.config.max_sentence_len, self.config.embed_size])
		print("Created embeddings tensor for the input")
		### END YOUR CODE
		return embeddings
        
	'''
	returns a list with lists containing the first words of all sentences, then the second words, then
	the third words, etc. [[a1, b1, c1], [a2, b2, c2], [a3, b3, c3]] for sentences [a1, a2, a3], [b1, b2, b3] etc
	'''
	def get_stacked_minibatches(self, tokenized_data, batch_size):
		batches = []
		prev_val = 0
		for step in xrange(batch_size, len(tokenized_data) + batch_size, batch_size):
			batch = tokenized_data[prev_val:step]
			prev_val = step
			batches.append( np.stack(batch, axis=1) )
		return batches

	def get_reg_minibatches(self, tokenized_data, batch_size):
		batches = []
		prev_val = 0
		for step in xrange(batch_size, len(tokenized_data) + batch_size, batch_size):
			batches.append( tokenized_data[prev_val:step] )
			prev_val = step
		return batches

	def test_stacked_minibatches():
		data = [[1,2,3,4], [1,2,3,4], [1,2,3,4]]
		result = get_minibatches(data, 2)
		assert result == [[[1,1],[2,2],[3,3],[4,4]],[[1],[2],[3],[4]]]
		print("minibatches function is correct")



	""" ELLIOTTS ADDITIONS
    We need two different functions for training and testing. At training time, the word vectors representing
    the headline are passed in as inputs to the decoder. At test time, the previous decoder output is passed
    into the next decoder cell's input. Function handles a single batch.
    """
	def add_pred_single_batch_train(self):
		x = self.encoder_inputs_placeholder # must be 1D list of int32 Tensors of shape [batch_size]
		y = self.labels_placeholder_list # must be 1D list of int32 Tensors of shape [batch_size]

		cell = tf.nn.rnn_cell.LSTMCell(encoder_hidden_size, initializer=tf.contrib.layers.xavier_initializer())

		#docs: https://www.tensorflow.org/api_docs/python/tf/contrib/legacy_seq2seq/embedding_attention_seq2seq

		outputs, state = tf.contrib.legacy_seq2seq.embedding_attention_seq2seq(x, y, cell, vocab_size, vocab_size, embed_size)
		"""
		outputs: A list of the same length as decoder_inputs of 2D Tensors with shape [batch_size x num_decoder_symbols] 
		containing the generated outputs
		"""
		return outputs # list (word by word) of 2D tensors: [batch_size, vocab_size]

	# Handles a single batch, returns the outputs
	def add_pred_single_batch_test(self):
		x = self.encoder_inputs_placeholder # must be 1D list of int32 Tensors of shape [batch_size]
		# TODO: change initialization of x. this placeholder cannot store a list of Tensors
        # don't have premade decoder inputs. will feed previous decoder output into next decoder cell's input

		# need to verify that this is initialized correctly
		cell = tf.nn.rnn_cell.LSTMCell(encoder_hidden_size, initializer=tf.contrib.layers.xavier_initializer())
		outputs, state = tf.contrib.legacy_seq2seq.embedding_attention_seq2seq(x, y, cell, vocab_size, vocab_size, embed_size, feed_previous=True)

		return outputs  # list (word by word) of 2D tensors: [batch_size, vocab_size]

	# assumes we already have padding implemented.


	def add_loss_op(self, preds):

		"""
		preds: [batch_size x max_sent_length x vocab_size] (need to convert output of legacy to tensor of this shape)
		labels: [batch_size x max_sentence_length] (IDs. either convert self.labels_placeholder, or save original input)

		"""
		#labels = # need to fill this in with rank 2 tensor with words as ID numbers. can save in config
		ce = tf.nn.sparse_softmax_cross_entropy_with_logits(labels, preds)
		# shape of ce: same as labels, with same type as preds [batch_size x max_sentence_length]
		ce = tf.boolean_mask(ce, self.mask_placeholder)
		loss = tf.reduce_mean(ce)

		return loss


	def add_training_op(self, loss):

		train_op = tf.train.AdadeltaOptimizer(self.config.lr).minimize(loss) # same optimizer as in IBM paper
		# Similar to Adagrad, which gives smaller updates to frequent params and larger updates to infrequent parameters.
		# Improves on Adagrad by addressing Adagrad's aggressive, monotonically decreasing learning rate.

		return train_op

	def tokenize_data(self, path, max_sentence_len, do_mask):
		tokenized_data = []
		masks = []
		f = open('data/summarization/' + path,'r')
		for line in f.readlines():
			sentence = [int(x) for x in line.split()]
			if len(sentence) > max_sentence_len:
				continue
			if do_mask:
				mask = [True] * len(sentence)
				mask.extend([False] * (max_sentence_len - len(sentence)))
				masks.append(mask)
			sentence.extend([PAD_ID] * (max_sentence_len - len(sentence)))
			tokenized_data.append(sentence)
		print("Tokenized " + path)
		print(tokenized_data)
		return tokenized_data, masks

	# 
	def train_on_batch(self, sess, inputs_batch, labels_batch, mask_batch):
        feed = self.create_feed_dict(inputs_batch, labels_batch=labels_batch, mask_batch=mask_batch)
        _, loss = sess.run([self.train_op, self.train_loss], feed_dict=feed)
        return loss

	def run_epoch(self, sess, train_data, dev_data):
        prog = Progbar(target=1 + int(len(train_examples) / self.config.batch_size))
        
        train_input, train_truth, train_mask = train_data
        dev_input, dev_truth, dev_mask = dev_data

        train_batches = get_stacked_minibatches(train_input, self.config.batch_size)
        truth_batches = get_stacked_minibatches(train_truth, self.config.batch_size)
        mask_batches = get_stacked_minibatches(train_mask, self.config.batch_size)

        for i, input_batch in enumerate(train_batches):
            loss = self.train_on_batch(sess, input_batch, truth_batches[i], mask_batches[i])
            prog.update(i + 1, [("train loss", loss)])
            if self.report: self.report.log_train_loss(loss)
        print("")

        logger.info("Evaluating on development data")
        token_cm, entity_scores = self.evaluate(sess, dev_set, dev_set_raw) # print loss on dev set

        f1 = entity_scores[-1]
        return f1

	def fit(self, sess):
		best_score = 0.

		#train_examples = self.preprocess_sequence_data(train_examples_raw)
		train_input_values, _ = tokenize_data('train.ids.sentence', self.config.max_sentence_len, False)
		train_ground_truth, train_ground_truth_mask = tokenize_data('train.ids.headline', self.config.max_sentence_len, True)

		#dev_set = self.preprocess_sequence_data(dev_set_raw)
		dev_input_values, _ = tokenize_data('val.ids.sentence', self.config.max_sentence_len, False)
		dev_ground_truth, dev_ground_truth_mask = tokenize_data('val.ids.headline', self.config.max_sentence_len, True)

		for epoch in range(self.config.n_epochs):
			logger.info("Epoch %d out of %d", epoch + 1, self.config.n_epochs)
			score = self.run_epoch(sess, (train_input_values, train_ground_truth, train_ground_truth_mask), \
									(dev_input_values, dev_ground_truth, dev_ground_truth_mask))
			if score > best_score:
				best_score = score
				if saver:
					logger.info("New best score! Saving model in %s", self.config.model_output)
					saver.save(sess, self.config.model_output)
			print("")
			
			if self.report:
				self.report.log_epoch()
				self.report.save()
			
		return best_score

	def build(self):
		self.add_placeholders()
		self.train_pred = self.add_pred_single_batch_train()
		self.train_loss = self.add_loss_op(self.train_pred)
		self.train_op = self.add_training_op(self.train_loss)

		self.dev_pred = self.add_pred_single_batch_test()
		self.dev_loss = self.add_loss_op(self.dev_pred)


	## Elliott's most recent additions 【=◈︿◈=】

	# dev_loss is likely to be much higher than train_loss, since we're feeding in prev outputs (instead of ground truth)
	# into the decoder
    def compute_dev_loss(self, sess, inputs_batch, labels_batch, mask_batch):
	    """Compute dev loss for a single batch

	    Args:
	        sess: tf.Session()
	        input_batch: np.ndarray of shape (n_samples, n_features)
	    Returns:
	        predictions: np.ndarray of shape (n_samples, n_classes)
	    """
	    feed = self.create_feed_dict(inputs_batch, labels_batch, mask_batch)
	    dev_loss = sess.run(self.dev_loss, feed_dict=feed)
    return dev_loss



if __name__ == '__main__':
	config = Config()
	rnn = RNN(config)
	rnn.build()

	'''	
	rnn.add_placeholders()
	rnn.create_feed_dict(input, ground_truth)
	rnn.encoder_decoder()
	'''

#GROUND TRUTH = HEADLINE
#INPUT = SENTENCE



'''
    def encoder(self):
    	fwd_cell = tf.nn.rnn_cell.LSTMCell(encoder_hidden_size, initializer=tf.contrib.layers.xavier_initializer())
    	bckwd_cell = tf.nn.rnn_cell.LSTMCell(encoder_hidden_size, initializer=tf.contrib.layers.xavier_initializer())
    	x = self.inputs_placeholder
    	outputs, output_states = tf.nn.bidirectional_dynamic_rnn(fwd_cell, bckwd_cell, x)
    	return tf.concat(output_states, 2)

   	def decoder(self, first_state):
   		x = self.inputs_placeholder
   		lstm_cell = tf.nn.rnn_cell.LSTMCell(decoder_hidden_size, initializer=tf.contrib.layers.xavier_initializer())
   		
   		tf.nn.seq2seq.attention_decoder(x, )

   		tf.nn.dynamic_rnn(lstm_cell, x, initial_state=first_state)
'''




'''
def prepare_data():
	path = "data/summarization/"
	data_files = [path + "train.ids.headline", path + "train.ids.summary"]
	queue = tf.train.string_input_producer(data_files, num_epochs=10)  		
	reader = tf.TextLineReader()
	key, value = reader.read(queue)
	tensor = tf.decode_raw(value, tf.int32)
	


	with tf.Session() as sess:
		sess.run(tf.global_variables_initializer())
		coord = tf.train.Coordinator()
  		threads = tf.train.start_queue_runners(coord=coord)
'''