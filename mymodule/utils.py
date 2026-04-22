import numpy as np

def get_contigs_idx(ar_input: np.typing.ArrayLike, topn: int)->np.typing.NDArray[np.int_]:
    '''
    this f identifies continuous stretches of 1s
    ar_input is an array of 0/1 vals, eg thryve's BBI status,
    which we transform like so df.Status.map({'LOW_CONFIDENCE':0, 'HIGH_CONFIDENCE':1})

    returns topn start:stop indices that indicate the beginning and the end of 1s stretch. Starting with the longest pair
    '''
    x=np.asarray(ar_input)
    a_diff = np.ediff1d(ary=x, to_begin=[0])
    starts = np.where(a_diff==1)[0]
    stops = np.where(a_diff==-1)[0]

    # a_idx contains pairs of vals, where first val is start idx, and second is end contig 1s
    if starts.shape[0] > stops.shape[0]: 
        # for when array is open-ended, ie high-conf values just keep going, we use  idx of last element for closing
        #a_idx = np.column_stack((starts[:-1],stops)) 
        a_idx = np.column_stack((starts, np.append(stops,values=[ar_input.shape[0]-1], axis=0))) 
    else: 
        a_idx = np.column_stack((starts,stops))
    
    a_contig_len = a_idx[:,1]-a_idx[:,0] 
    
    if topn>a_contig_len.shape[0]: # if we ask for too many idx pairs, just return all we have
        topn=a_contig_len.shape[0]
    idx=np.argsort(a_contig_len)[-1*topn:] # get topn idx of contig arrays with highest vals

    return a_idx[idx][::-1]