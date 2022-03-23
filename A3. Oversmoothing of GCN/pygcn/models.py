import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.nn.parameter import Parameter
from pygcn.layers import GraphConvolution
import numpy as np
import math

class GraphConvolution(nn.Module):

    def __init__(self, in_features, out_features, residual=True, variant=True):
        super(GraphConvolution, self).__init__()
        self.variant = variant
        if self.variant:
            self.in_features = 2*in_features
        else:
            self.in_features = in_features

        self.out_features = out_features
        self.residual = residual
        self.weight = Parameter(torch.FloatTensor(self.in_features,self.out_features))
        self.reset_parameters()
        self.fc = nn.Linear(16, 1,bias=True)

    def reset_parameters(self):
        stdv = 1. / math.sqrt(self.out_features)
        self.weight.data.uniform_(-stdv, stdv)

    def forward(self, input, adj , h0 , lamda, l):
        hi = torch.spmm(adj, input)
        alpha = self.fc(hi)
        theta = math.log(lamda/l+1)
        if self.variant:
            support = torch.cat([hi,h0],1)
            r = (1-alpha)*hi+alpha*h0
        else:
            support = (1-alpha)*hi+alpha*h0
            r = support
        output = theta*torch.mm(support, self.weight)+(1-theta)*r
        if self.residual:
            output = output+input
        return output

class GCN(nn.Module):
    def __init__(self, nfeat, nhid, nclass, num_layers, dropout):
        super(GCN, self).__init__()
        self.convs = torch.nn.ModuleList()
        self.convs.append(GraphConvolution(nfeat, nhid))
        for _ in range(num_layers -2):
            self.convs.append(GraphConvolution(nhid, nhid))
        self.convs.append(GraphConvolution(nhid, nclass))
        self.dropout = dropout
        self.num_layers = num_layers

    def reset_parameters(self):
        for conv in self.convs:
            conv.reset_parameters()

    def forward(self, x, adj):
        for conv in self.convs[:-1]:
            x = conv(x,adj)
            x = F.relu(x)
            x = F.dropout(x, p = self.dropout, training = self.training)
        x = self.convs[-1](x,adj)
        np.save(f'embedding/GCNalphafree_{self.num_layers}',x.cpu().detach().numpy())

        return F.log_softmax(x, dim=1)

class ResidualGCN(nn.Module):
    def __init__(self, nfeat, nhid, nclass, num_layers, dropout):
        super(ResidualGCN, self).__init__()
        self.convs = torch.nn.ModuleList()
        self.convs.append(GraphConvolution(nfeat, nhid))
        for _ in range(num_layers -2):
            self.convs.append(GraphConvolution(nhid, nhid))
        self.convs.append(GraphConvolution(nhid, nclass))
        self.dropout = dropout
        self.num_layers = num_layers

    def reset_parameters(self):
        for conv in self.convs:
            conv.reset_parameters()

    def forward(self, x, adj):
        for conv in self.convs[:-1]:
            x = conv(x,adj)
            x_i = x
            x = F.relu(x)
            x = F.dropout(x, p = self.dropout, training = self.training)
            # x = x_i+x
            # x = torch.mul(x_i,x)
        x = self.convs[-1](x,adj)
        np.save(f'alphafree_{self.num_layers}',x.cpu().detach().numpy())

        return F.log_softmax(x, dim=1)

class GCNII(nn.Module):
    def __init__(self, nfeat, nlayers, nhidden, nclass, dropout,lamda, variant):
        super(GCNII, self).__init__()
        self.convs = nn.ModuleList()
        for _ in range(nlayers):
            self.convs.append(GraphConvolution(nhidden, nhidden,variant=variant))
        self.fcs = nn.ModuleList()
        self.fcs.append(nn.Linear(nfeat, nhidden))
        self.fcs.append(nn.Linear(nhidden, nclass))
        self.params1 = list(self.convs.parameters())
        self.params2 = list(self.fcs.parameters())
        self.act_fn = nn.ReLU()
#        self.act_fn = nn.SiLU()
        self.dropout = dropout
#        self.alpha = alpha
        self.lamda = lamda
        self.num_layers = nlayers

    def forward(self, x, adj):
        _layers = []
        x = F.dropout(x, self.dropout, training=self.training)
        layer_inner = self.act_fn(self.fcs[0](x))
        _layers.append(layer_inner)
        for i,con in enumerate(self.convs):
            layer_inner = F.dropout(layer_inner, self.dropout, training=self.training)
            layer_inner = self.act_fn(con(layer_inner,adj,_layers[0],self.lamda,i+1))
        layer_inner = F.dropout(layer_inner, self.dropout, training=self.training)
        layer_inner = self.fcs[-1](layer_inner)
        np.save(f'embedding/alphafree_{self.num_layers}', layer_inner.cpu().detach().numpy())
        return F.log_softmax(layer_inner, dim=1)