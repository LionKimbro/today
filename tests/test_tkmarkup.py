import unittest

from today import tkmarkup


GUID_A = "{550e8400-e29b-41d4-a716-446655440000}"
GUID_B = "{44a5ac91-bac9-4570-a62f-56575c54566b}"


class TkMarkupTests(unittest.TestCase):
    def test_parses_elements_and_paragraph_boundaries(self):
        elements = tkmarkup.parse_text("# Heading\na\nb\n\n[ ] item " + GUID_A + "\n>>> " + GUID_B)
        self.assertEqual([element["type"] for element in elements], ["HEADING", "PARAGRAPH", "BLANK", "ITEM", "PROMPT"])
        self.assertEqual(elements[1]["text"], "a b")
        self.assertEqual(elements[3]["title"], "item")

    def test_link_is_a_distinct_identity_bearing_element(self):
        source = "[link] Lion [https://example.com]"
        normalized = tkmarkup.normalize_text(source)
        link = tkmarkup.parse_text(normalized)[0]
        self.assertEqual(link["type"], "LINK")
        self.assertEqual(link["title"], "Lion")
        self.assertEqual(link["url"], "https://example.com")
        self.assertTrue(tkmarkup.is_valid_guid(link["guid"]))

    def test_normalization_is_idempotent_and_preserves_malformed_text(self):
        source = "[ ] Repair {bad}\n>>> " + GUID_A + "\n[x] Again " + GUID_A
        normalized = tkmarkup.normalize_text(source)
        self.assertEqual(tkmarkup.normalize_text(normalized), normalized)
        self.assertIn("Repair {bad} {", normalized)
        guids = [element["guid"] for element in tkmarkup.parse_text(normalized) if element["type"] in {"ITEM", "PROMPT"}]
        self.assertEqual(len(guids), len(set(guids)))

    def test_mutations_preserve_unrelated_source_and_block_boundaries(self):
        source = "# H\n[ ] One " + GUID_A + "\n[>] Two " + GUID_B + "\n\n>>> {342083fa-782d-4323-bc61-0f9d147044ec}\n"
        cycled = tkmarkup.cycle_item(source, GUID_A)
        self.assertIn("[>] One " + GUID_A, cycled)
        self.assertEqual(tkmarkup.move_item(source, GUID_A, -1), source)
        moved = tkmarkup.move_item(source, GUID_A, 1)
        self.assertIn("[>] Two " + GUID_B + "\n[ ] One " + GUID_A, moved)
        added = tkmarkup.add_item(source, "{342083fa-782d-4323-bc61-0f9d147044ec}", "  New item  ")
        self.assertIn("[ ] New item {", added)
        self.assertEqual(tkmarkup.delete_item(source, "{missing}"), source)

    def test_blocked_state_never_cycles(self):
        source = "[-] Blocked " + GUID_A
        self.assertEqual(tkmarkup.cycle_item(source, GUID_A), source)


if __name__ == "__main__":
    unittest.main()
