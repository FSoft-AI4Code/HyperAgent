def concat_strings(list_a, list_b, sep=" : ", align=True):
    """
    Concatenates elements from two lists into a new list of strings, combining corresponding elements with a separator.

    Parameters:
        list_a (list): The first list containing elements to be combined.
        list_b (list): The second list containing elements to be combined.
        sep (str, optional): The separator to be used between elements. Default is " : ".
        align (bool, optional): If True, aligns the elements in the output list by padding the first list's elements
                                with spaces to match the width of the longest element. If False, no alignment is applied.
                                Default is True.

    Returns:
        list of str: A new list of strings combining elements from list_a and list_b.

    Example:
        list_a = ['1', '2', '33']
        list_b = ['a', 'b', 'ccc']
        concat_strings(list_a, list_b, sep=" : ", align=True)
        Output: [' 1 : a', ' 2 : b', '33 : ccc']
    """
    assert len(list_a) == len(list_b), "Input sequences should have the same length"
    str_list_a = list(map(str, list_a))
    str_list_b = list(map(str, list_b))
    if align:
        max_width_a = max(map(len, str_list_a))
        return [f"{s_a:>{max_width_a}}{sep}{s_b}"
          for s_a, s_b in zip(str_list_a, str_list_b)]
    else:
        return [f"{s_a}{sep}{s_b}"
          for s_a, s_b in zip(str_list_a, str_list_b)]
    
def repeated_subsequences(sequence, min_repetition=5, prefix=None):
    """
    repeated_subsequences([0, 1, 2, 3, 1, 1, 1, 1, 3, 3, 5, 2, 5, 2 ,5, 2, 5, 2, 5, 2, 5, 2, 5,2, 5, 2, 5,2, 5, 2, 5,], min_repetition=4)
    [{'subsequence': [5, 2], 'start': 10, 'end': 29, 'num_repetition': 10, 'subsequence_length': 2, 'total_length': 20}, {'subsequence': [1], 'start': 4, 'end': 7, 'num_repetition': 4, 'subsequence_length': 1, 'total_length': 4}]
    """

    subsequences = []
    max_subseq_length = int(len(sequence)/min_repetition)
    for current_subseq_length in range(1, max_subseq_length):
        previous_end = None
        for i in range(len(sequence) - current_subseq_length):
            if previous_end and i <= previous_end:
                continue
            current_subseq = sequence[i:i+current_subseq_length]
            k = 1 
            end = i +current_subseq_length-1
            while i+current_subseq_length*(k+1) <= len(sequence):
                if current_subseq == sequence[i+current_subseq_length*k:i+current_subseq_length*(k+1)]:
                    end = i+current_subseq_length*(k+1)-1
                    k += 1
                else:
                    break
    
            if k >= min_repetition:
                if prefix is None or all([elem.startswith(prefix) for elem in current_subseq]):
                    subsequences.append({
                        "subsequence": current_subseq,
                        "start": i,
                        "end": end,
                        "num_repetition": k,
                        "subsequence_length": len(current_subseq),
                        "total_length": len(current_subseq) * k
                    })
                    previous_end = end
    
    # remove subsumed
    # preferred: longer total length, shorter subsequence length
    subsequences.sort(key=lambda elem: (-elem["total_length"], elem["subsequence_length"]))
    remainings = list(range(len(subsequences)))
    removed = None
    while removed is None or len(removed) > 0:
        removed = []
        for i in range(len(remainings)):
            this = subsequences[remainings[i]]
            for j in range(i+1, len(remainings)):
                if j in removed:
                    continue
                other = subsequences[remainings[j]]
                if other["end"] < this["start"] or this["end"] < other["start"]: # not overlapped
                    pass
                else:
                    removed.append(j)
        remainings = [remainings[i] for i in range(len(remainings)) if i not in removed]
    return [subsequences[i] for i in remainings]
