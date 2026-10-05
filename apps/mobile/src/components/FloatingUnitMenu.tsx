import { useState, type ReactNode } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';

export type UnitMenuAnchor = { x: number; y: number; width: number; height: number };

export function floatingMenuPosition(anchor: UnitMenuAnchor, viewportWidth: number, viewportHeight: number, menuHeight: number) {
  const width = Math.min(200, viewportWidth - 16);
  const below = Math.max(0, viewportHeight - anchor.y - anchor.height - 12);
  const above = Math.max(0, anchor.y - 12);
  const opensBelow = below >= menuHeight || below >= above;
  const maxHeight = Math.max(44, Math.min(menuHeight, opensBelow ? below : above, viewportHeight - 16));
  return {
    left: Math.max(8, Math.min(anchor.x, viewportWidth - width - 8)),
    top: Math.max(8, Math.min(opensBelow ? anchor.y + anchor.height + 4 : anchor.y - maxHeight - 4, viewportHeight - maxHeight - 8)),
    width,
    maxHeight,
  };
}

/** Modal keeps the anchored menu outside scroll content and prevents layout movement. */
export function FloatingUnitMenu({ anchor, children, label, onClose }: {
  anchor: UnitMenuAnchor;
  children: ReactNode;
  label: string;
  onClose: () => void;
}) {
  const viewport = useWindowDimensions();
  const [menuHeight, setMenuHeight] = useState(266);
  const position = floatingMenuPosition(anchor, viewport.width, viewport.height, menuHeight);
  return (
    <Modal transparent visible animationType="none" onRequestClose={onClose}>
      <View style={styles.overlay}>
        <Pressable accessibilityLabel="Close unit menu" accessibilityRole="button" onPress={onClose} style={StyleSheet.absoluteFill} />
        <View accessibilityLabel={label} style={[styles.menu, position]}>
          <ScrollView keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}
            onContentSizeChange={(_, height) => setMenuHeight(height + 2)}>
            {children}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1 },
  menu: {
    position: 'absolute', backgroundColor: '#FFFFFF', borderColor: '#D6EAE0',
    borderRadius: 10, borderWidth: 1, overflow: 'hidden',
    elevation: 8, boxShadow: '0px 4px 14px rgba(1, 44, 45, 0.16)',
  },
});
