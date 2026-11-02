namespace MathesisPilot
theorem lean_list_append_nil : ∀ {α : Type} (l : List α), l ++ [] = l := by
  intro l
  simp
end MathesisPilot
