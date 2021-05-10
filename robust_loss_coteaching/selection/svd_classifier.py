import torch
import numpy as np
from sklearn import cluster
from tqdm import tqdm
from .gmm import *
from .util import *

__all__=['get_singular_vector', 'cleansing', 'fine', 'extract_cleanidx']


def get_singular_vector(features, labels):
    '''
    To get top1 sigular vector in class-wise manner by using SVD of hidden feature vectors
    features: hidden feature vectors of data (numpy)
    labels: correspoding label list
    '''
    
    singular_vector_dict = {}
    with tqdm(total=len(np.unique(labels))) as pbar:
        for index in np.unique(labels):
            _, _, v = np.linalg.svd(features[labels==index])
            singular_vector_dict[index] = v[0]
            pbar.update(1)

    return singular_vector_dict


def get_score(singular_vector_dict, features, labels, normalization=True):
    '''
    Calculate the score providing the degree of showing whether the data is clean or not.
    '''
    if normalization:
        scores = [np.abs(np.inner(singular_vector_dict[labels[indx]], feat/np.linalg.norm(feat))) for indx, feat in enumerate(tqdm(features))]
    else:
        scores = [np.abs(np.inner(singular_vector_dict[labels[indx]], feat)) for indx, feat in enumerate(tqdm(features))]
        
    return np.array(scores)

def extract_topk(scores, labels, k):
    '''
    k: ratio to extract topk scores in class-wise manner
    To obtain the most prominsing clean data in each classes
    
    return selected labels 
    which contains top k data
    '''
    
    indexes = torch.tensor(range(len(labels)))
    selected_labels = []
    for cls in np.unique(labels):
        num = int(p * np.sum(labels==cls))
        _, sorted_idx = torch.sort(scores[labels==cls], descending=True)
        selected_labels += indexes[labels==cls][sorted_idx[:num]].numpy().tolist()
        
    return torch.tensor(selected_labels, dtype=torch.int64)

def cleansing(scores, labels):
    '''
    Assume the distribution of scores: bimodal spherical distribution.
    
    return clean labels 
    that belongs to the clean cluster made by the KMeans algorithm
    '''
    
    indexes = np.array(range(len(scores)))
    clean_labels = []
    for cls in np.unique(labels):
        cls_index = indexes[labels==cls]
        kmeans = cluster.KMeans(n_clusters=2, random_state=0).fit(scores[cls_index].reshape(-1, 1))
        if np.mean(scores[cls_index][kmeans.labels_==0]) < np.mean(scores[cls_index][kmeans.labels_==1]): kmeans.labels_ = 1 - kmeans.labels_
            
        clean_labels += cls_index[kmeans.labels_ == 0].tolist()
        
    return np.array(clean_labels, dtype=np.int64)
        

def fine(current_features, current_labels, fit = 'kmeans', prev_features=None, prev_labels=None):
    '''
    prev_features, prev_labels: data from the previous round
    current_features, current_labels: current round's data
    
    return clean labels
    
    if you insert the prev_features and prev_labels to None,
    the algorthm divides the data based on the current labels and current features
    
    '''
    if (prev_features != None) and (prev_labels != None):
        singular_vector_dict = get_singular_vector(prev_features, prev_labels)
    else:
        singular_vector_dict = get_singular_vector(current_features, current_labels)

    scores = get_score(singular_vector_dict, features = current_features, labels = current_labels)
    
    if 'kmeans' in fit:
        clean_labels = cleansing(scores, current_labels)
    elif 'gmm' in fit:
        clean_labels = fit_mixture(scores, current_labels)
    else:
        raise NotImplemented
    
    return clean_labels

def extract_cleanidx(teacher, data_loader, parse, print_statistics = True):
    teacher.load_state_dict(torch.load('./checkpoint/' + parse.load_name)['state_dict'])
    teacher = teacher.cuda()

    if not parse.reinit: teacher.load_state_dict(torch.load('./checkpoint/' + parse.load_name)['state_dict'])
    for params in teacher.parameters(): params.requires_grad = False
    
    if 'fine' in parse.distill_mode:
        features, labels = get_features(teacher, data_loader)
        clean_labels = fine(current_features=features, current_labels=labels, fit = parse.distill_mode)
    elif 'loss' in parse.distill_mode:
        clean_labels, labels = cleansing_loss(teacher, data_loader)
    else:
        raise NotImplemented
    if print_statistics: return_statistics(data_loader, clean_labels, datanum=len(labels))
    
    
    return clean_labels
