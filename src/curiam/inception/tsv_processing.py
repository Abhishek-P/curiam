"""Functions for processing the TSV-formatted data exported from Inception."""


from typing import Tuple


def process_compound_label(label):
    """Splits a multi-part token label and returns the separate category labels
    (and which annotation they belong to)."""

    sublabels = label.split("|")
    categories = []
    annotation_indexes = []
    for sublabel in sublabels:
        # If annotation isn't indexed , it only covers a single token and there's only one label
        # Give these an annotation_index of -1.

        # Spans that are only a single token that are part of some longer span still get indexed,
        # like Focal Term[59] below.

        """
        62-32	8336-8337	"	*[56]|*[58]	Example Use[56]|Direct Quote[58]
        62-33	8338-8342	same	*[56]|*[58]|*[59]	Example Use[56]|Direct Quote[58]|Focal Term[59]
        62-34	8343-8344	"	*[56]|*[58]	Example Use[56]|Direct Quote[58]
        """

        # If there are two overlapping single-token annotations,
        # the format is "Appeal to Meaning[1]|Metalinguistic Cue[2]"
        if "[" not in sublabel:
            categories.append(sublabel)
            annotation_indexes.append(-1)
        else:
            bracket_index = sublabel.index("[")
            categories.append(sublabel[:bracket_index])
            annotation_indexes.append(int(sublabel[bracket_index+1:-1]))
    return categories, annotation_indexes


def process_sentence(tsv_rows: list) -> list:
    """Parse TSV rows for a sentence into a list of simplified TSV rows.

    Each simplified row contains:
    - Sentence number
    - Token
    - Label(s)

    The format of the labels is "{category}:{index}" and if a token has multiple
    labels, they are separated by a pipe ("|").

    Reindexes annotations from document level to sentence level.

    Example: "Direct Quote[82]|Direct Quote[83]" is a label for a token that is part of a nested direct quote.
    Assuming 82 is the first annotation of the sentence, the result will be:
        categories= ["Direct Quote", "Direct Quote"]
        annotation_indexes = [1, 2]

    """
    simplified_rows = []
    index_offset = -1_000_000
    for row in tsv_rows:
        cells = row.split("\t")
        # 0-th cell has sent num and token num separated by hyphen
        sent_num = cells[0][:cells[0].index("-")]
        token = cells[2]
        label = cells[4]
        if label == "_":
            simplified_rows.append(f"{sent_num}\t{token}\t_")
        else:
            categories, annotation_indexes = process_compound_label(label)
            if index_offset == -1_000_000:
                index_offset = annotation_indexes[0] - 1
            new_label = ""
            for category, index, in zip(categories, annotation_indexes):
                if index == -1:
                    new_label += f"{category}:{index}|"
                else:
                    # New label has a colon to separate categories from indexes and a pipe between each sublabel
                    new_label += f"{category}:{index-index_offset}|"
            # Remove extra pipe at end of new_label
            simplified_rows.append(f"{sent_num}\t{token}\t{new_label[:-1]}")
    return simplified_rows


def process_opinion_file(filepath: str) -> list:
    """Parses a TSV export from Inception.

    Returns a list of lists of tokens (i.e. a list of sentences).

    Tokens are represented as simplified TSV rows containing the sentence
    number, the token string, and the token's annotated labels."""

    with open(filepath, "r", encoding="utf-8") as f:
        data = f.readlines()

    # Make sure sentences start in expected place
    assert data[4].startswith("#Text")

    doc_rows = []
    sent_rows = []
    for row in data[4:]:
        # Start of a new sentence, but we don't need to do anything with this line
        if row.startswith("#Text"):
            sent_rows = []

        # End of sentence reached
        elif row == "\n":
            simplified_rows = process_sentence(sent_rows)
            doc_rows.append(simplified_rows)

        # Token row
        else:
            sent_rows.append(row)

    doc = [[token.split("\t") for token in sent] for sent in doc_rows]

    return doc


def get_annotations(sentence: list, annotation_column: int) -> Tuple[list, list]:
    # This is the final product, containing [category, start, stop] entries
    annotations = []

    # For keeping track of multi-token annotations
    indexed_annotations = {}
    for i, token in enumerate(sentence):
        label = token[annotation_column]
        if "*" in label:
            # These aren't correct; investigate
            print(token)
            break
        if label == "_":  # No annotation
            continue
        elif "-1" in label:  # "-1" means it's a single-token annotation (e.g. "Metalinguistic Cue:-1")
            category = label[:label.index(":")]
            annotations.append([category, i, i])
        else:
            token_annotations = label.split("|")
            for annotation in token_annotations:
                category, index = annotation.split(":")
                index = int(index)

                # Add annotation to list of indexed annotations with start and stop indexes
                if annotation not in indexed_annotations.keys():
                    indexed_annotations[annotation] = [category, i, i]

                # Update the end index the next time we see this annotation
                else:
                    indexed_annotations[annotation][2] = i
    for value in indexed_annotations.values():
        annotations.append(value)
    return annotations
