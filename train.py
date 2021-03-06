#!/usr/bin/env python3

import matplotlib
matplotlib.use('Agg')

import argparse
from methods.utils import load_data, sample_training_set, similarity_callback, plot_loss_acc
from sklearn.preprocessing import LabelBinarizer
from methods.graphSemiCNN import GraphSemiCNN
import numpy as np
import progressbar
from sklearn.metrics import classification_report
from sklearn.metrics import precision_recall_curve
import pickle

def main():
    parser = argparse.ArgumentParser(description="This script is for training the semi-supervised neural network model")
    parser.add_argument('-e', '--exp', required=True, help='path to input gene expression data, with genes in rows and samples in columns')
    parser.add_argument('-l', '--label', required=True, help='path to input labels')
    parser.add_argument('-m', '--model', required=True, help='path to output trained model')
    parser.add_argument('-b', '--label_bin', required=True, help='path to output label binarizer')
    parser.add_argument('-p', '--plot', required=True, help='path to output accuracy/loss plot')
    parser.add_argument('-c', '--epochs', default=75, type=int, help='number of epochs to train for')
    args = parser.parse_args()

    # params
    exp_path = args.exp
    label_path = args.label
    model_path = args.model
    label_bin_path = args.label_bin
    plot_path = args.plot
    nb_epochs = args.epochs
    
    nb_neighbors = 2
    sample_size = 10000
    seed = 42
    valid_size = 10
    batch_size = 64
    
    # load data, shuffle the samples, and scale data
    dat = load_data(exp_path, label_path)
    
    # construct the KNN graph, sample context distribution, and split the data (60% trn; 20% val; 20% tst)
    trn, val, tst = sample_training_set(dat, sample_size)
        
    # one-hot encoding
    lb = LabelBinarizer()
    lb.fit(dat['out']) # labels
    trn['out'][0] = lb.transform(trn['out'][0])
    val_label = val['out'][0]
    val['out'][0] = lb.transform(val['out'][0])
    tst['out'][0] = lb.transform(tst['out'][0])
    nb_classes = len(lb.classes_) # note: training classes vs data classes
    
    # build and train the model
    print('[INFO] building and training the model...')
    nb_samples = trn['inp'][0].shape[0]
    nb_genes = trn['inp'][0].shape[1]
    np.random.seed(seed)
    model, val_model = GraphSemiCNN().build(nb_genes, nb_classes)    
    
    ind = np.random.randint(len(val['smp'][0]), size=valid_size)
    smp_val = {'smp': val['smp'][0][ind], 'inp': val['inp'][0][ind], 'out': val_label[ind]}
    
    history = {new_list: [] for new_list in ['loss', 'out1_acc', 'out2_acc', 'val_loss', 'val_out1_acc', 'val_out2_acc']}
    ind = np.arange(nb_samples)
    ind_list = [ind[i * batch_size:(i + 1) * batch_size] for i in range((len(ind) + batch_size - 1) // batch_size)]
    
    print('Train on %s samples, validate on %s samples' % (nb_samples, val['inp'][0].shape[0]))
    for e in range(nb_epochs):
        print('Epoch %s/%s...' % (e + 1, nb_epochs))
        # train on batch
        for i in range(len(ind_list)):
            trainX = [trn['inp'][0][ind_list[i]], trn['inp'][1][ind_list[i]]]
            trainY = [trn['out'][0][ind_list[i]], trn['out'][1][ind_list[i]]]
            validX = [val['inp'][0], val['inp'][1]]
            validY = [val['out'][0], val['out'][1]]
            loss = model.train_on_batch(trainX, trainY)
        # validate on batch
        val_loss = model.evaluate(validX, validY, batch_size=batch_size, verbose=0)
        print('- loss: %.4f - out1_acc: %.4f - out2_acc: %.4f - val_loss: %.4f - val_out1_acc: %.4f - val_out2_acc: %.4f \n' % 
                (loss[0], loss[2], loss[3], val_loss[0], val_loss[2], val_loss[3]))
        print(similarity_callback(valid_size, smp_val, dat, val_model) + '\n')
        history['loss'].append(loss[0])
        history['out1_acc'].append(loss[2])
        history['out2_acc'].append(loss[3])
        history['val_loss'].append(val_loss[0])
        history['val_out1_acc'].append(val_loss[2])
        history['val_out2_acc'].append(val_loss[3])


    # evaluate the model
    print('[INFO] evaluating the model...')
    predictions = model.predict(tst['inp'], batch_size=batch_size)
    print(classification_report(tst['out'][0].argmax(axis=1),
	predictions[0].argmax(axis=1), labels=range(len(lb.classes_)), target_names=lb.classes_))

    # plot the training loss and accuracy
    plot_loss_acc(plot_path, nb_epochs, history)

    # save the model and label binarizer
    print('[INFO] serializing the model and label binarizer...')
    model.save(model_path)
    f = open(label_bin_path, 'wb')
    f.write(pickle.dumps(lb))
    f.close()

if __name__ == "__main__":
    main()

