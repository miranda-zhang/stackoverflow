def peaks_valleys(seq):
     if len(seq) < 3:
         return 0
     count = 0
     for i in range(1, len(seq)-1):
         if seq[i-1] < seq[i] > seq[i+1]:
             count += 1
         elif seq[i-1] > seq[i] < seq[i+1]:
             count += 1
     return count
