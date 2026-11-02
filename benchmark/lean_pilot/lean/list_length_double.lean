namespace MathesisPilot
theorem lean_list_length_double : ∀ {α : Type} (l : List α), (l ++ l.reverse).length = 2 * l.length := by
  intro α
  intro l
  have h1 : (l ++ l.reverse).length = l.length + l.reverse.length := List.length_append
  have h2 : l.reverse.length = l.length := List.length_reverse
  omega
end MathesisPilot
