import csv
import io


def pairing_csv(export):
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['run_id', 'checksum', 'revision', 'visitor_code', 'reading_order', 'old_ok', 'new_ok', 'complete'])
    for row in export['snapshot']['pairs']:
        old, new = row['old_ok'], row['new_ok']
        writer.writerow([export['id'], export['checksum'], export['revision'], row['visitor_code'],
                         row['reading_order'], old, new, old is not None and new is not None])
    return output.getvalue()
