'''
This script is used to fix encodings for misencoded CSV files.
	1.	Load a CSV file with potentially broken characters.
	2.	Fix all misencoded text (like √© instead of é) by reversing the mojibake.
	3.	Save the corrected file to a new path.
'''

import csv
from ftfy import fix_text

input_file = "public/new_filtered_news_300_700_words.csv"
output_file = "public/test3_encoding_fixed_300_700_words.csv"

with open(input_file, 'r', encoding='utf-8', errors='replace') as infile, \
     open(output_file, 'w', encoding='utf-8', newline='') as outfile:

    reader = csv.reader(infile)
    writer = csv.writer(outfile)

    for row in reader:
        fixed_row = [fix_text(cell) for cell in row]
        writer.writerow(fixed_row)

print("Mojibake fixed with ftfy. Saved to:", output_file)

'''
def fix_mojibake(input_file, output_file):
    with open(input_file, 'r', encoding='latin1', errors='replace') as f:
        content = f.read()

    # Attempt to reverse mojibake by encoding and decoding again properly
    fixed = content.encode('latin1', errors='replace').decode('utf-8', errors='replace')

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(fixed)

    print(f"File cleaned and saved as UTF-8: {output_file}")

# Example usage
fix_mojibake(input_file, output_file)
'''