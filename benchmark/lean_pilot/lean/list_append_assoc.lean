namespace MathesisPilot
theorem lean_list_append_assoc : ∀ {α : Type} (l1 l2 l3 : List α), (l1 ++ l2) ++ l3 = l1 ++ (l2 ++ l3) := by
  intro α
  intro l1
  intro l2
  intro l3
  exact List.append_assoc l1 l2 l3
end MathesisPilot
