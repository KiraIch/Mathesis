import unittest

from mathesis import proof_rules as pr


class StripCommentsTest(unittest.TestCase):
    def test_line_comment(self):
        text, open_ = pr.strip_lean_comments("  simp -- sorry here\n  ring")
        self.assertFalse(open_)
        self.assertNotIn("sorry", text)
        self.assertEqual(text.count("\n"), 1)
        self.assertIn("ring", text)

    def test_block_and_doc_comment(self):
        for src in ("/- sorry -/ simp", "/-- sorry -/ simp", "simp /-\nsorry\n-/"):
            text, open_ = pr.strip_lean_comments(src)
            self.assertFalse(open_)
            self.assertNotIn("sorry", text)
        # newlines inside a comment survive, so line numbers do not move
        self.assertEqual(pr.strip_lean_comments("a /-\n\n-/ b")[0].count("\n"), 2)

    def test_nested_block_comment(self):
        text, open_ = pr.strip_lean_comments("/- /- -/ axiom -/ simp")
        self.assertFalse(open_)
        self.assertNotIn("axiom", text)
        self.assertIn("simp", text)

    def test_unterminated_block_comment(self):
        text, open_ = pr.strip_lean_comments("simp /- never closed sorry")
        self.assertTrue(open_)
        self.assertNotIn("sorry", text)
        # nested: the inner close does not end the outer comment
        self.assertTrue(pr.strip_lean_comments("/- /- -/ simp")[1])

    def test_comment_symbols_inside_string_are_kept(self):
        src = 'trace "-- not a comment" ; sorry'
        text, open_ = pr.strip_lean_comments(src)
        self.assertFalse(open_)
        self.assertEqual(text, src)
        src = 'trace "/- still a string" ; sorry'
        self.assertEqual(pr.strip_lean_comments(src), (src, False))

    def test_string_escapes(self):
        src = r'trace "a \" -- b" ; sorry'
        self.assertEqual(pr.strip_lean_comments(src), (src, False))

    def test_char_literal_quote_does_not_open_a_string(self):
        text, _ = pr.strip_lean_comments("""exact f '"' -- sorry\n  rfl""")
        self.assertNotIn("sorry", text)
        self.assertIn("rfl", text)

    def test_prime_in_identifier_is_not_a_char_literal(self):
        text, _ = pr.strip_lean_comments("exact h' -- sorry\n  exact h''")
        self.assertNotIn("sorry", text)
        self.assertIn("h''", text)

    def test_raw_string_is_opaque(self):
        for src in ('r#"a"--"# axiom x : False', 'r"--" sorry', 'r##"x"# -- y"## sorry',
                    'r#"/- "# sorry'):
            self.assertEqual(pr.strip_lean_comments(src), (src, False), src)

    def test_raw_string_does_not_hide_following_code(self):
        self.assertEqual(pr.find_forbidden_in_proof('r#"a"--"# axiom x : False'), "axiom")
        self.assertEqual(pr.find_forbidden_in_proof('r"--" sorry'), "sorry")
        self.assertEqual(pr.find_forbidden_in_proof('\n  trace r#"x"# ; sorry -- c'), "sorry")

    def test_guillemet_identifier_is_opaque(self):
        src = "«a--b» axiom"
        self.assertEqual(pr.strip_lean_comments(src), (src, False))
        self.assertEqual(pr.find_forbidden_in_proof(src), "axiom")
        self.assertEqual(pr.find_forbidden_in_proof("«a/-b» sorry"), "sorry")

    def test_unclosed_raw_string_and_guillemet_keep_the_rest(self):
        for src in ('r#"abc -- sorry', "«abc -- sorry", 'r"abc /- sorry'):
            self.assertEqual(pr.strip_lean_comments(src), (src, False), src)
            self.assertEqual(pr.find_forbidden_in_proof(src), "sorry")

    def test_r_is_only_a_raw_string_start_outside_identifiers(self):
        # `bar"` / `r` as identifier end or plain `r` are not raw strings.
        text, _ = pr.strip_lean_comments('exact bar -- sorry\n  exact r')
        self.assertNotIn("sorry", text)
        text, _ = pr.strip_lean_comments("exact r -- sorry")
        self.assertNotIn("sorry", text)
        text, _ = pr.strip_lean_comments("exact r# -- sorry")
        self.assertNotIn("sorry", text)

    def test_existing_prime_and_string_cases_unchanged(self):
        text, _ = pr.strip_lean_comments("exact h' -- sorry\n  exact h''")
        self.assertNotIn("sorry", text)
        self.assertIn("h''", text)

    def test_comment_separates_tokens(self):
        self.assertIsNone(pr.find_forbidden_in_proof("exact sor/- -/ry"))
        self.assertIsNone(pr.find_forbidden_in_proof("exact sor--\nry"))


class ForbiddenTest(unittest.TestCase):
    def test_interpolated_string_desync_falls_back_to_raw_text(self):
        # Review case: the stripper would end the string at the '"' char literal and
        # then treat "/- " as a block comment hiding the axiom command.
        text = "s!\"{ '\"' } /- \"\naxiom foo : False\n-- -/"
        self.assertEqual(pr.find_forbidden_in_proof(text), "axiom")
        self.assertEqual(pr.find_forbidden_in_proof("exact '\"'\n-- -/ axiom"), "axiom")
        # Fallback is stricter: a commented token now counts when the construct appears.
        self.assertEqual(pr.find_forbidden_in_proof("exact s!\"x\" -- sorry"), "sorry")

    def test_comment_only_token_not_forbidden(self):
        self.assertIsNone(pr.find_forbidden_in_proof("\n  simp -- no axiom needed"))
        self.assertIsNone(pr.find_forbidden_in_proof("\n  /- sorry -/ simp"))

    def test_code_token_forbidden(self):
        self.assertEqual(pr.find_forbidden_in_proof("axiom foo : False"), "axiom")
        self.assertEqual(pr.find_forbidden_in_proof("\n  /- ok -/ sorry"), "sorry")
        self.assertEqual(pr.find_forbidden_in_proof('\n  trace "-- x"\n  admit'), "admit")

    def test_unterminated_comment_is_forbidden(self):
        self.assertEqual(
            pr.find_forbidden_in_proof("\n  simp /- oops"), pr.UNTERMINATED_COMMENT
        )

    def test_output_is_checked_verbatim(self):
        out = "f.lean:3:8: warning: declaration uses 'sorry'"
        self.assertEqual(pr.find_forbidden(out), "sorry")
        self.assertEqual(pr.find_forbidden("-- sorry"), "sorry")


if __name__ == "__main__":
    unittest.main()
