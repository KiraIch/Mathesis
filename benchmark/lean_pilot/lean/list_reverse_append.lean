namespace MathesisPilot
theorem lean_list_reverse_append : ∀ {α : Type} (l1 l2 : List α), (l1 ++ l2).reverse = l2.reverse ++ l1.reverse := by
  intro α
  intro l1
  intro l2
  exact List.reverse_append
end MathesisPilot
