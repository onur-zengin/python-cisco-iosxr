#!/usr/bin/env python

import re
import os
import gzip

def _GzipnRotate(log_retention):
    unzipped_logfiles = filter(lambda file: re.search(r'pniMonitor_cron.log.*[^gz]$', file),
                               os.listdir(os.getcwd()))
    for file in unzipped_logfiles:
        with open(file) as ulf:
            contents = ulf.read()
            with gzip.open(file + '.gz','w') as zlf:
                zlf.write(contents)
        main_logger.info('%s compressed and saved.', file)
        os.remove(file)
    zipped_logfiles = {file: os.stat(file).st_mtime for file in
                       filter(lambda file: re.search(r'pniMonitor_(main|ssh).log.*[gz]$', file),
                              os.listdir(os.getcwd()))}
    if len(zipped_logfiles) > int(log_retention):
        sortedlogfiles = sorted(zipped_logfiles.items(), key=operator.itemgetter(1))
        for file in sortedlogfiles[:(len(zipped_logfiles)-int(log_retention))]:
            os.remove(file[0])
            main_logger.info('%s removed.', file[0])


