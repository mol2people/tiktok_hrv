import numpy as np

def get_contigs_idx(ar_input: np.typing.ArrayLike, top_n: int, get_high: bool):
    '''
    get start idx, end idx, and lengths of unbroken runs of 1s/Os
    ar_input is eg df['Status'].map({'HIGH_CONFIDENCE':1, 'LOW_CONFIDENCE':0})
    get_high=True returns 1s, =False 0s
    top_n is num longest contigs to get

    returns 3 arrays
    '''
    a=np.asarray(ar_input, dtype=np.int8)

    change=np.flatnonzero(np.ediff1d(a))+1 # +1 to get correct idx, since ediff1d 'skips' the first elem
    begin=np.empty(change.size+1, dtype=np.uint32) # up to max=4_294_967_295 for 32bits, up to max**2 for uint64 
    end=np.empty(change.size+1, dtype=np.uint32)

    begin[0]=0
    begin[1:]=change
    end[:-1]=change
    end[-1]=a.size

    lens=end-begin 
    vals=a[begin]

    if get_high:
        mask=(vals==1)
    else: mask=(vals==0)

    if top_n>begin.size: # if ask too many contig arrays, just return all we have
        top_n=begin.size

    idx=np.argsort(lens[mask])[-1*top_n:]

    return begin[mask][idx][::-1], end[mask][idx][::-1], lens[mask][idx][::-1]

def rr_to_bpm(rr_ms: np.typing.ArrayLike):
    '''
    convert R-R [ms] array into bpm, error-proof for div by zero and nans
    '''
    rr_ms = np.asarray(rr_ms, dtype=float)
    return np.divide(60_000, rr_ms, out=np.full_like(rr_ms, np.nan), where=(rr_ms!=0))

def bpm_to_rr(bpm: np.typing.ArrayLike):
    '''
    convert bpm array to R-R [ms] array, error-proof for div by zero and nans
    '''
    bpm = np.asarray(bpm, dtype=float)
    return np.divide(60_000, bpm, out=np.full_like(bpm, np.nan), where=(bpm!=0))