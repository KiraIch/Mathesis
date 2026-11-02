namespace MathesisPilot
theorem lean_list_length_append : ∀ {α : Type} (l1 l2 : List α), (l1 ++ l2).length = l1.length + l2.length := by
  intro α
  intro l1
  intro l2
  exact List.length_append
end MathesisPilot
