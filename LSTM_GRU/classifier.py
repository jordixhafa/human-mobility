import torch
import numpy as np
from torch import nn

from data_loader import DataLoader
from helper import ValTest
from modality_lstm import ModalityLSTM
import time
import pandas as pd
pd.options.mode.chained_assignment = None  # default='warn'



t_start = time.clock()



batch_size = 16 #32
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
train_on_gpu = True
output_size = 5
hidden_dim = 256
trip_dim = 7
n_layers = 3
drop_prob = 0.2
net = ModalityLSTM(trip_dim, output_size, batch_size, hidden_dim, n_layers, train_on_gpu, drop_prob, lstm_drop_prob=0.2)
lr= 0.001 #0.001 #learning rate
loss_function = nn.CrossEntropyLoss(ignore_index=-1)
optimizer = torch.optim.Adam(net.parameters(), lr=lr)
epochs = 10 #6
print_every = 5
log_every = 1
evaluate_every = 100

clip = 0.2 # gradient clipping

if train_on_gpu:
    net.cuda()
net.train()

dl = DataLoader(batchsize=batch_size, read_from_pickle=True)
dl.prepare_data()

def pad_trajs(trajs, lengths):
    for w, elem in enumerate(trajs):
        while len(elem) < lengths[0]:
            elem.append([-1] * trip_dim)
    return trajs


losses, avg_losses = [], []

validator = ValTest(dl.val_batches, net, trip_dim, batch_size, device, loss_function, output_size, dl.get_val_size())
test = ValTest(dl.test_batches, net, trip_dim, batch_size, device, loss_function, output_size, dl.get_test_size())

for e in range(1,epochs+1):
    print(' ')
    print("epoch ",e)
    hidden = net.init_hidden()
    counter = 0
    torch.cuda.empty_cache()
    for train_sorted, labels_sorted in dl.batches():
        counter += 1
        lengths = [len(x) for x in train_sorted]
        train_sorted = pad_trajs(train_sorted, lengths)

        X = np.asarray(train_sorted, dtype=np.float)
        input_tensor = torch.from_numpy(X)
        input_tensor = input_tensor.to(device)

        net.zero_grad()
        output, max_padding_for_this_batch = net(input_tensor, lengths)

        for labelz in labels_sorted:
            while len(labelz) < max_padding_for_this_batch:
                labelz.append(-1)

        labels_for_loss = torch.tensor(labels_sorted).view(max_padding_for_this_batch * batch_size, -1).squeeze(
            1).long().to(device)

        loss = loss_function(output.view(
                            max_padding_for_this_batch*batch_size, -1),
                            labels_for_loss)
        loss.backward()
        nn.utils.clip_grad_norm_(net.parameters(), clip)
        optimizer.step()

        if counter % log_every == 0:
            losses.append(loss.item())
        if counter % print_every == 0:
            avg_losses.append(sum(losses[-50:]) / 50)
            #print(
             #   f'Epoch: {e:2d}. {counter:d} of {int(dl.get_train_size() / batch_size):d} {avg_losses[len(avg_losses) - 1]:f} Loss: {loss.item():.4f}')
        if counter % evaluate_every == 0:
            validator.run()

t_end = time.clock()
print(' ')
print('Temps Training: ', t_end - t_start)

print(' ')
print(' ')
print("Testing")
t_start = time.clock()
test.run()
t_end = time.clock()
print(' ')
print('Temps: ', t_end - t_start)