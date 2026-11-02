namespace MathesisPilot
theorem lean_list_map_append : ∀ {α β : Type} (f : α → β) (l1 l2 : List α), List.map f (l1 ++ l2) = List.map f l1 ++ List.map f l2 := by
  intro α
  intro β
  intro f
  intro l1
  intro l2
  exact List.map_append
end MathesisPilot
