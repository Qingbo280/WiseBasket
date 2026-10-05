import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFonts } from 'expo-font';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  type ImageSourcePropType,
} from 'react-native';
import {
  priceCheckLocationFontAssets,
  priceCheckLocationTokens,
} from '../components/price-check/priceCheckLocationTokens';
import { BasketItemImage } from '../components/BasketItemImage';
import { FloatingUnitMenu, type UnitMenuAnchor } from '../components/FloatingUnitMenu';
import { foodImageUriForBackendId } from '../data/foodAssetManifest';
import { filterPriceCheckCatalog } from './priceCheckProductSearchContent';
import type { PriceCheckCatalogEntry } from '../services/priceCheckCatalogApi';
import { newReceiptClientLineId, type ReceiptConfirmation } from '../services/receiptApi';
import { loadReceiptReviewDraft, saveReceiptReviewDraft } from '../services/receiptReviewDraft';
import { groupReceiptReviewRows, selectedReceiptGroupRowIds, updateReceiptReviewGroup } from '../services/receiptReviewGroups';
import {
  defaultReceiptManualQuantity,
  initialSelectedReceiptRowIds, isLockedConfirmedReceiptRow,
  markReceiptRowReviewed,
  prepareReceiptConfirmation,
  prefillReceiptCandidateRows,
  rankedReceiptCandidateEntries,
  RECEIPT_UNIT_OPTIONS, replaceReceiptRowFood,
} from '../services/receiptReviewRows';

const RECEIPT_UNIT_LABELS: Record<(typeof RECEIPT_UNIT_OPTIONS)[number], string> = {
  kg: 'Kilograms',
  g: 'Grams',
  L: 'Litres',
  ml: 'Millilitres',
  pcs: 'Pieces',
  pack: 'Packs',
};

export interface ReceiptReviewItem {
  productId: string;
  name: string;
  imageSource: ImageSourcePropType | null;
  suggestedQuantity: number;
  unit: string;
}

export type ReceiptReviewLine = {
  id: string;
  lineId: string | null;
  clientLineId?: string | null;
  foodId: string | null;
  name: string;
  price: number | null;
  quantityKg: number | null;
  quantityUnit: string | null;
  quantityInput?: string;
  quantityEdited?: boolean;
  quantityEstimated?: boolean;
  quantityPriceEstimated?: boolean;
  quantityHeuristicEstimated?: boolean;
  priceInput?: string;
  aggregateInput?: { memberKey: string; quantityInput?: string; priceInput?: string };
  rawName?: string;
  printedPackCount?: number | null;
  printedPackageG?: number | null;
  purchaseCountHint?: number | null;
  reviewStatus?: string;
  imageSource?: ImageSourcePropType | null;
  candidateFoodIds?: readonly string[];
  suggestedOnly?: boolean;
};

export interface ReceiptReviewScreenProps {
  receiptId?: string;
  catalogItems?: readonly PriceCheckCatalogEntry[];
  catalogMessage?: string;
  catalogStatus?: 'loading' | 'ready' | 'error';
  initialLines?: readonly ReceiptReviewLine[];
  onBack?: () => void;
  onConfirm?: (items: readonly ReceiptReviewItem[], confirmation: ReceiptConfirmation) => void;
}

function imageSourceForFoodId(foodId: string | null): ImageSourcePropType | null {
  if (!foodId) return null;
  const imageUri = foodImageUriForBackendId(foodId);
  return imageUri ? { uri: imageUri } : null;
}

function parseOptionalDecimal(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed || trimmed === '.') return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

function StepIndicator() {
  return (
    <View accessibilityLabel="Receipt step 3 of 3" style={styles.stepIndicator}>
      <View style={[styles.step, styles.completeStep]}>
        <MaterialCommunityIcons color={COLORS.white} name="check" size={15} />
        <Text style={[styles.stepLabel, styles.completeStepText]}>Capture</Text>
      </View>
      <View style={[styles.stepLine, styles.completeStepLine]} />
      <View style={[styles.step, styles.completeStep]}>
        <MaterialCommunityIcons color={COLORS.white} name="check" size={15} />
        <Text style={[styles.stepLabel, styles.completeStepText]}>Process</Text>
      </View>
      <View style={[styles.stepLine, styles.completeStepLine]} />
      <View style={[styles.step, styles.activeStep]}>
        <Text style={[styles.stepText, styles.activeStepText]}>3</Text>
        <Text style={[styles.stepLabel, styles.activeStepText]}>Review</Text>
      </View>
    </View>
  );
}

function formatPrice(price: number | null) {
  return price === null ? 'Price not found' : `RM ${price.toFixed(2)}`;
}

function formatQuantity(quantityKg: number | null, quantityUnit: string | null) {
  return quantityKg === null || quantityUnit === null ? 'Amount unknown' : `${quantityKg} ${quantityUnit}`;
}

export function ReceiptReviewScreen({
  receiptId,
  catalogItems = [],
  catalogMessage,
  catalogStatus = 'ready',
  initialLines = [],
  onBack,
  onConfirm,
}: ReceiptReviewScreenProps) {
  const [fontsLoaded] = useFonts(priceCheckLocationFontAssets);
  const [lines, setLines] = useState<ReceiptReviewLine[]>(() => [...initialLines]);
  const [selectedIds, setSelectedIds] = useState<readonly string[]>(() => initialSelectedReceiptRowIds(initialLines));
  const [showAddMissing, setShowAddMissing] = useState(false);
  const [catalogQuery, setCatalogQuery] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [replacementLineId, setReplacementLineId] = useState<string | null>(null);
  const [replacementQuery, setReplacementQuery] = useState('');
  const [unitPickerLineId, setUnitPickerLineId] = useState<string | null>(null);
  const [unitPickerAnchor, setUnitPickerAnchor] = useState<UnitMenuAnchor | null>(null);
  const unitPickerRefs = useRef(new Map<string, View>());
  const [draftLoaded, setDraftLoaded] = useState(false);

  useEffect(() => {
    if (catalogItems.length === 0) return;
    // The candidate's name/image become a suggested initial value. Do not add
    // its row to selectedIds: only an explicit tap or replacement confirms it.
    setLines((current) => prefillReceiptCandidateRows(current, catalogItems));
  }, [catalogItems]);

  useEffect(() => {
    if (!receiptId) {
      setDraftLoaded(true);
      return;
    }
    let active = true;
    void loadReceiptReviewDraft(receiptId).then((draft) => {
      if (!active || !draft) return;
      const persistedServerIds = new Set(initialLines.map((line) => line.clientLineId));
      const restored = draft.manualLines.filter((line) => !persistedServerIds.has(line.clientLineId));
      setLines((current) => {
        const currentIds = new Set(current.map((line) => line.clientLineId ?? line.id));
        return [...current, ...restored.filter((line) => !currentIds.has(line.clientLineId ?? line.id))];
      });
      setSelectedIds((current) => [
        ...new Set([...current, ...draft.selectedManualIds.filter((id) => restored.some((row) => row.id === id))]),
      ]);
    }).catch(() => {
      // Storage failure must not block receipt review.
    }).finally(() => {
      if (active) setDraftLoaded(true);
    });
    return () => { active = false; };
  }, [receiptId]);

  useEffect(() => {
    if (!receiptId || !draftLoaded) return;
    void saveReceiptReviewDraft(
      receiptId,
      lines.filter((line) => line.lineId === null),
      selectedIds.filter((id) => lines.some((line) => line.id === id && line.lineId === null)),
    ).catch(() => {});
  }, [receiptId, draftLoaded, lines, selectedIds]);

  const selectedIdSet = useMemo(
    () => selectedReceiptGroupRowIds(lines, new Set(selectedIds)), [lines, selectedIds],
  );
  const displayLines = useMemo(() => groupReceiptReviewRows(lines), [lines]);
  const selectedLines = displayLines.filter((line) => selectedIdSet.has(line.id));
  const selectedTotal = lines.filter((line) => selectedIdSet.has(line.id))
    .reduce((total, line) => total + (line.price ?? 0), 0);
  const searchResults = useMemo(
    () => filterPriceCheckCatalog(catalogItems, catalogQuery).slice(0, 8),
    [catalogItems, catalogQuery],
  );
  const replacementLine = displayLines.find((line) => line.id === replacementLineId) ?? null;
  const replacementResults = useMemo(() => {
    if (replacementQuery.trim()) {
      return filterPriceCheckCatalog(catalogItems, replacementQuery).slice(0, 8);
    }
    if (!replacementLine?.candidateFoodIds?.length) return [];
    return rankedReceiptCandidateEntries(catalogItems, replacementLine.candidateFoodIds).slice(0, 4);
  }, [catalogItems, replacementLine, replacementQuery]);

  const toggleLine = (id: string) => {
    if (lines.some((line) => line.id === id && isLockedConfirmedReceiptRow(line))) return;
    const ids = displayLines.find((line) => line.id === id)?.sourceRowIds ?? [id];
    setLines((current) => ids.reduce((rows, memberId) => markReceiptRowReviewed(rows, memberId), current));
    setSelectedIds((current) => (
      ids.every((memberId) => current.includes(memberId))
        ? current.filter((selectedId) => !ids.includes(selectedId))
        : [...new Set([...current, ...ids])]
    ));
  };

  const updateLine = (id: string, patch: Partial<ReceiptReviewLine>) => {
    const group = displayLines.find((line) => line.id === id);
    if (!group) return;
    setLines((current) => {
      const updated = updateReceiptReviewGroup(current, group, patch);
      return 'price' in patch ? prefillReceiptCandidateRows(updated, catalogItems) : updated;
    });
  };

  const addMissingItem = (entry: PriceCheckCatalogEntry) => {
    const id = newReceiptClientLineId();
    setLines((current) => [...current, {
      id,
      lineId: null,
      clientLineId: id,
      foodId: entry.foodId,
      name: entry.name,
      price: null,
      ...defaultReceiptManualQuantity(entry),
      rawName: 'Added manually',
      imageSource: entry.imageSource,
    }]);
    setSelectedIds((current) => [...current, id]);
    setCatalogQuery('');
  };

  const replaceLineFood = (lineId: string, entry: PriceCheckCatalogEntry) => {
    if (lines.some((line) => line.id === lineId && isLockedConfirmedReceiptRow(line))) return;
    const ids = displayLines.find((line) => line.id === lineId)?.sourceRowIds ?? [lineId];
    setLines((current) => ids.reduce((rows, id) => replaceReceiptRowFood(rows, id, {
      foodId: entry.foodId,
      name: entry.name,
      imageSource: entry.imageSource,
      suggestedOnly: false,
      purchasePriceRmPer100g: entry.purchasePriceRmPer100g,
      minPurchasePriceRmPer100g: entry.minPurchasePriceRmPer100g,
      soldByWeight: entry.soldByWeight,
      quantityG: entry.quantityG,
      subtitle: entry.subtitle,
    }), current));
    setSelectedIds((current) => [...new Set([...current, ...ids])]);
    setReplacementLineId(null);
    setReplacementQuery('');
  };

  const handleConfirm = () => {
    const confirmedLines = selectedLines.filter(
      (line) => line.foodId !== null,
    );
    const { confirmation, invalidLineIds } = prepareReceiptConfirmation(lines, selectedIdSet);
    if (invalidLineIds.length > 0) {
      Alert.alert('Check quantity and unit',
        'Enter a positive quantity and a unit for every selected item before confirming. Check items marked Amount unknown.');
      setIsEditing(true);
      return;
    }
    onConfirm?.(confirmedLines.map((line): ReceiptReviewItem => ({
      productId: `receipt-${line.id}`,
      name: line.name,
      imageSource: line.imageSource ?? imageSourceForFoodId(line.foodId),
      suggestedQuantity: line.quantityKg ?? 0,
      unit: line.quantityKg === null ? 'amount unknown' : (line.quantityUnit ?? 'amount unknown'),
    })), confirmation);
  };

  if (!fontsLoaded) {
    return <View style={styles.fontLoading} />;
  }

  return (
    <View style={styles.wrapper}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.header}>
          <Pressable
            accessibilityLabel="Back to receipt processing"
            accessibilityRole="button"
            onPress={onBack}
            style={({ pressed }) => [styles.headerButton, pressed && styles.pressed]}
          >
            <MaterialCommunityIcons color={COLORS.deepTeal} name="arrow-left" size={27} />
          </Pressable>
          <Text style={styles.headerTitle}>Review purchase</Text>
          <View style={styles.headerButton} />
        </View>

        <StepIndicator />

        <View style={styles.headingBlock}>
          <Text accessibilityRole="header" style={styles.pageTitle}>Check what we found</Text>
          <Text style={styles.pageSubtitle}>Review each item before it goes into What You Have.</Text>
        </View>

        <View style={styles.summaryCard}>
          <View style={styles.summaryIcon}>
            <MaterialCommunityIcons color={COLORS.green} name="receipt-text-check-outline" size={25} />
          </View>
          <View style={styles.summaryCopy}>
            <Text style={styles.summaryTitle}>Receipt ready to confirm</Text>
            <Text style={styles.summarySubtitle}>{selectedLines.length} of {displayLines.length} items selected</Text>
          </View>
          <Text style={styles.summaryTotal}>RM {selectedTotal.toFixed(2)}</Text>
        </View>

        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Items from your receipt</Text>
          <Pressable
            accessibilityLabel={isEditing ? 'Done editing' : 'Modify items'}
            accessibilityRole="button"
            onPress={() => {
              setIsEditing((current) => !current);
              setUnitPickerLineId(null);
            }}
            style={({ pressed }) => [styles.modifyButton, pressed && styles.pressed]}
          >
            <MaterialCommunityIcons color={COLORS.deepTeal} name={isEditing ? 'check' : 'pencil-outline'} size={17} />
            <Text style={styles.modifyButtonText}>{isEditing ? 'Done' : 'Modify items'}</Text>
          </Pressable>
        </View>

        <View style={styles.itemCard}>
          {displayLines.map((line, index) => {
            const selected = selectedIdSet.has(line.id);
            const confirmed = isLockedConfirmedReceiptRow(line);
            return (
              <View key={line.id} style={[styles.itemRow, index === displayLines.length - 1 && styles.lastItemRow]}>
                <Pressable
                  accessibilityLabel={`${line.name}, ${selected ? 'included' : 'excluded'}`}
                  accessibilityRole="checkbox"
                  accessibilityState={{ checked: selected }}
                  disabled={line.foodId === null || confirmed}
                  onPress={() => toggleLine(line.id)}
                  style={({ pressed }) => [styles.checkboxButton, pressed && styles.rowPressed]}
                >
                  <MaterialCommunityIcons
                    color={selected ? COLORS.green : COLORS.muted}
                    name={selected ? 'checkbox-marked-circle-outline' : 'checkbox-blank-circle-outline'}
                    size={28}
                  />
                </Pressable>
                <View style={styles.itemImageFrame}>
                  <BasketItemImage
                    imageSource={line.imageSource ?? imageSourceForFoodId(line.foodId)}
                    name={line.name}
                    resizeMode="contain"
                    style={styles.itemImage}
                  />
                </View>
                <View style={styles.itemCopy}>
                  <Text style={[styles.itemName, !selected && styles.mutedItemText]}>{line.name}</Text>
                  {isEditing ? (
                    <View style={styles.editFields}>
                      <View style={styles.editFieldsRow}>
                        <View style={styles.editInputGroup}>
                          <TextInput
                            accessibilityLabel={`${line.name} quantity`}
                            editable={!confirmed}
                            keyboardType="decimal-pad"
                            onChangeText={(value) => updateLine(line.id, {
                              quantityInput: value,
                              quantityKg: parseOptionalDecimal(value),
                              quantityEdited: true,
                              quantityPriceEstimated: false, quantityHeuristicEstimated: false,
                            })}
                            placeholder="0"
                            placeholderTextColor={COLORS.muted}
                            style={styles.editInput}
                            value={line.quantityInput ?? (line.quantityKg === null ? '' : String(line.quantityKg))}
                          />
                          <Pressable
                            ref={(ref) => { if (ref) unitPickerRefs.current.set(line.id, ref); else unitPickerRefs.current.delete(line.id); }}
                            accessibilityLabel={`Choose unit for ${line.name}`}
                            accessibilityRole="button"
                            accessibilityState={{ expanded: unitPickerLineId === line.id }}
                            disabled={confirmed}
                            onPress={() => {
                              setReplacementLineId(null);
                              unitPickerRefs.current.get(line.id)?.measureInWindow((x, y, width, height) => {
                                setUnitPickerAnchor({ x, y, width, height });
                                setUnitPickerLineId(line.id);
                              });
                            }}
                            style={({ pressed }) => [styles.unitDropdown, pressed && styles.rowPressed]}
                          >
                            <Text style={[styles.unitDropdownText, !line.quantityUnit && styles.unitDropdownPlaceholder]}>
                              {line.quantityUnit ?? 'Select'}
                            </Text>
                            <MaterialCommunityIcons
                              color={COLORS.muted}
                              name={unitPickerLineId === line.id ? 'chevron-up' : 'chevron-down'}
                              size={16}
                            />
                          </Pressable>
                        </View>
                        <View style={styles.editInputGroup}>
                          <Text style={styles.inputUnit}>RM</Text>
                          <TextInput
                            accessibilityLabel={`${line.name} price in RM`}
                            keyboardType="decimal-pad"
                            onChangeText={(value) => updateLine(line.id, {
                              priceInput: value, price: parseOptionalDecimal(value),
                            })}
                            placeholder="0.00"
                            placeholderTextColor={COLORS.muted}
                            style={styles.editInput}
                            value={line.priceInput ?? (line.price === null ? '' : String(line.price))}
                          />
                        </View>
                      </View>
                      {unitPickerLineId === line.id && unitPickerAnchor ? (
                        <FloatingUnitMenu anchor={unitPickerAnchor} label={`Units for ${line.name}`} onClose={() => setUnitPickerLineId(null)}>
                          {RECEIPT_UNIT_OPTIONS.map((option) => {
                            const active = line.quantityUnit?.trim().toLowerCase() === option.toLowerCase();
                            return (
                              <Pressable
                                accessibilityLabel={`Set ${line.name} unit to ${RECEIPT_UNIT_LABELS[option]}`}
                                accessibilityRole="button"
                                accessibilityState={{ selected: active }}
                                key={option}
                                onPress={() => {
                                  updateLine(line.id, { quantityUnit: option, quantityEdited: true,
                                    quantityPriceEstimated: false, quantityHeuristicEstimated: false });
                                  setUnitPickerLineId(null);
                                }}
                                style={({ pressed }) => [
                                  styles.unitOptionRow,
                                  active && styles.unitOptionRowActive,
                                  pressed && styles.rowPressed,
                                ]}
                              >
                                <Text style={[styles.unitOptionText, active && styles.unitOptionTextActive]}>
                                  {RECEIPT_UNIT_LABELS[option]} ({option})
                                </Text>
                                {active ? <MaterialCommunityIcons color={COLORS.green} name="check" size={17} /> : null}
                              </Pressable>
                            );
                          })}
                        </FloatingUnitMenu>
                      ) : null}
                      <Pressable
                        accessibilityLabel={`Change ${line.name}`}
                        accessibilityRole="button"
                        disabled={confirmed}
                        onPress={() => {
                          setUnitPickerLineId(null);
                          setReplacementLineId((current) => current === line.id ? null : line.id);
                          setReplacementQuery('');
                        }}
                        style={({ pressed }) => [styles.changeItemButton, pressed && styles.rowPressed]}
                      >
                        <MaterialCommunityIcons color={COLORS.deepTeal} name="pencil-outline" size={15} />
                        <Text style={styles.changeItemText}>Change item</Text>
                      </Pressable>
                      {replacementLineId === line.id ? (
                        <View style={styles.replacementPicker}>
                          <TextInput
                            accessibilityLabel={`Search for the correct food for ${line.name}`}
                            autoFocus
                            onChangeText={setReplacementQuery}
                            placeholder="Search for the correct food"
                            placeholderTextColor={COLORS.muted}
                            style={styles.replacementSearch}
                            value={replacementQuery}
                          />
                          {!replacementQuery.trim() && replacementResults.length > 0 ? (
                            <Text style={styles.replacementHint}>Suggestions</Text>
                          ) : null}
                          {replacementResults.map((entry) => (
                            <Pressable
                              accessibilityLabel={`Use ${entry.name} for ${line.name}`}
                              accessibilityRole="button"
                              key={entry.foodId}
                              onPress={() => replaceLineFood(line.id, entry)}
                              style={({ pressed }) => [styles.replacementResult, pressed && styles.rowPressed]}
                            >
                              <Text style={styles.replacementResultName}>{entry.name}</Text>
                              <MaterialCommunityIcons color={COLORS.green} name="check-circle-outline" size={19} />
                            </Pressable>
                          ))}
                          {catalogStatus === 'ready' && replacementQuery.trim() && replacementResults.length === 0 ? (
                            <Text style={styles.replacementHint}>No matching food found.</Text>
                          ) : null}
                        </View>
                      ) : null}
                    </View>
                  ) : (
                    <Text style={styles.itemQuantity}>{line.quantityPriceEstimated || line.quantityHeuristicEstimated ? '~' : ''}{formatQuantity(line.quantityKg, line.quantityUnit)}</Text>
                  )}
                </View>
                {!isEditing ? <Text style={[styles.itemPrice, !selected && styles.mutedItemText]}>{formatPrice(line.price)}</Text> : null}
              </View>
            );
          })}
        </View>

        <Pressable
          accessibilityLabel="Add missing item"
          accessibilityRole="button"
          onPress={() => setShowAddMissing((current) => !current)}
          style={({ pressed }) => [styles.addMissingButton, pressed && styles.pressed]}
        >
          <MaterialCommunityIcons color={COLORS.deepTeal} name="plus-circle-outline" size={22} />
          <Text style={styles.addMissingText}>Add missing item</Text>
          <MaterialCommunityIcons color={COLORS.deepTeal} name={showAddMissing ? 'chevron-up' : 'chevron-down'} size={21} />
        </Pressable>
        {showAddMissing ? (
          <View style={styles.catalogCard}>
            <Text style={styles.catalogTitle}>Search all foods</Text>
            <TextInput
              accessibilityLabel="Search food catalogue"
              onChangeText={setCatalogQuery}
              placeholder="Search rice, chicken, garlic..."
              placeholderTextColor={COLORS.muted}
              style={styles.catalogSearch}
              value={catalogQuery}
            />
            {catalogStatus === 'loading' ? <Text style={styles.catalogHint}>Loading foods...</Text> : null}
            {catalogStatus === 'error' ? <Text style={styles.catalogHint}>{catalogMessage ?? 'Food catalogue unavailable.'}</Text> : null}
            {catalogStatus === 'ready' && searchResults.length === 0 ? <Text style={styles.catalogHint}>No matching food found.</Text> : null}
            {searchResults.map((entry) => (
              <Pressable
                accessibilityLabel={`Add ${entry.name}`}
                accessibilityRole="button"
                key={entry.foodId}
                onPress={() => addMissingItem(entry)}
                style={({ pressed }) => [styles.catalogRow, pressed && styles.rowPressed]}
              >
                <View style={styles.catalogImageFrame}>
                  <BasketItemImage imageSource={entry.imageSource} name={entry.name} style={styles.catalogImage} />
                </View>
                <View style={styles.catalogCopy}>
                  <Text style={styles.catalogName}>{entry.name}</Text>
                  <Text style={styles.catalogSubtitle}>{entry.subtitle ?? 'Amount unknown'}</Text>
                </View>
                <MaterialCommunityIcons color={COLORS.green} name="plus" size={21} />
              </Pressable>
            ))}
          </View>
        ) : null}

        <Pressable
          accessibilityLabel="Confirm purchase"
          accessibilityRole="button"
          disabled={selectedLines.length === 0}
          onPress={handleConfirm}
          style={({ pressed }) => [styles.primaryButton, selectedLines.length === 0 && styles.disabledButton, pressed && styles.pressed]}
        >
          <MaterialCommunityIcons color={COLORS.white} name="check-circle-outline" size={24} />
          <Text style={styles.primaryButtonText}>Confirm purchase</Text>
        </Pressable>
        <Text style={styles.footerHint}>Confirmed items will appear in What You Have.</Text>
      </ScrollView>
    </View>
  );
}

const COLORS = {
  background: priceCheckLocationTokens.colors.background,
  deepTeal: priceCheckLocationTokens.colors.deepTeal,
  green: '#2D806B',
  mint: '#E8F8EF',
  muted: priceCheckLocationTokens.colors.secondaryText,
  paleMint: '#F1F8F4',
  white: '#FFFFFF',
} as const;

const styles = StyleSheet.create({
  activeStep: { backgroundColor: COLORS.deepTeal },
  activeStepText: { color: COLORS.white },
  addMissingButton: { alignItems: 'center', backgroundColor: COLORS.paleMint, borderRadius: 16, flexDirection: 'row', gap: 8, justifyContent: 'center', marginTop: 14, minHeight: 50, paddingHorizontal: 15 },
  addMissingText: { color: COLORS.deepTeal, fontFamily: priceCheckLocationTokens.fonts.bodySemibold, fontSize: 14 },
  catalogCard: { backgroundColor: COLORS.white, borderColor: '#DCEBE1', borderRadius: 18, borderWidth: 1, marginTop: 8, padding: 12 },
  catalogCopy: { flex: 1, minWidth: 0 },
  catalogHint: { color: COLORS.muted, fontFamily: priceCheckLocationTokens.fonts.body, fontSize: 12, paddingVertical: 10 },
  catalogImage: { height: 38, width: 38 },
  catalogImageFrame: { alignItems: 'center', backgroundColor: COLORS.paleMint, borderRadius: 10, height: 42, justifyContent: 'center', width: 42 },
  catalogName: { color: COLORS.deepTeal, fontFamily: priceCheckLocationTokens.fonts.bodySemibold, fontSize: 14 },
  catalogRow: { alignItems: 'center', borderTopColor: '#E4EFE8', borderTopWidth: 1, flexDirection: 'row', gap: 10, minHeight: 58, paddingVertical: 8 },
  catalogSearch: { backgroundColor: COLORS.paleMint, borderColor: '#DCEBE1', borderRadius: 12, borderWidth: 1, color: COLORS.deepTeal, fontFamily: priceCheckLocationTokens.fonts.body, fontSize: 13, minHeight: 42, paddingHorizontal: 12 },
  catalogSubtitle: { color: COLORS.muted, fontFamily: priceCheckLocationTokens.fonts.body, fontSize: 11, marginTop: 2 },
  catalogTitle: { color: COLORS.deepTeal, fontFamily: priceCheckLocationTokens.fonts.bodySemibold, fontSize: 14, marginBottom: 8 },
  changeItemButton: { alignItems: 'center', alignSelf: 'flex-start', flexDirection: 'row', gap: 4, marginTop: 7, paddingVertical: 3 },
  changeItemText: { color: COLORS.deepTeal, fontFamily: priceCheckLocationTokens.fonts.bodySemibold, fontSize: 12 },
  checkboxButton: { alignItems: 'center', justifyContent: 'center', minHeight: 36, width: 30 },
  completeStep: { backgroundColor: COLORS.green },
  completeStepLine: { backgroundColor: COLORS.green },
  completeStepText: { color: COLORS.white },
  content: { paddingBottom: 36, paddingHorizontal: 24 },
  disabledButton: { backgroundColor: '#AAB8B5' },
  editFields: { marginTop: 5 },
  editFieldsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  editInput: { backgroundColor: 'transparent', color: COLORS.deepTeal, flex: 1, fontFamily: priceCheckLocationTokens.fonts.body, fontSize: 12, minHeight: 31, minWidth: 0, paddingHorizontal: 0, width: 0 },
  editInputGroup: { alignItems: 'center', backgroundColor: COLORS.paleMint, borderColor: '#D6EAE0', borderRadius: 8, borderWidth: 1, flex: 1, flexBasis: 120, flexDirection: 'row', minHeight: 31, minWidth: 120, paddingHorizontal: 8 },
  fontLoading: { backgroundColor: COLORS.background, flex: 1 },
  footerHint: { color: COLORS.muted, fontFamily: priceCheckLocationTokens.fonts.body, fontSize: 12, lineHeight: 17, marginTop: 10, textAlign: 'center' },
  header: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between', minHeight: 64 },
  headerButton: { alignItems: 'center', height: 48, justifyContent: 'center', width: 48 },
  headerTitle: { color: COLORS.deepTeal, fontFamily: priceCheckLocationTokens.fonts.bodySemibold, fontSize: 16 },
  headingBlock: { paddingTop: 24 },
  itemCard: { backgroundColor: COLORS.white, borderColor: '#DCEBE1', borderRadius: 20, borderWidth: 1, overflow: 'hidden' },
  itemCopy: { flex: 1, minWidth: 0 },
  itemImage: { height: 48, width: 48 },
  itemImageFrame: { alignItems: 'center', backgroundColor: COLORS.paleMint, borderRadius: 12, height: 52, justifyContent: 'center', overflow: 'hidden', width: 52 },
  itemName: { color: COLORS.deepTeal, fontFamily: priceCheckLocationTokens.fonts.cardTitle, fontSize: 15, lineHeight: 19 },
  itemPrice: { color: COLORS.deepTeal, fontFamily: priceCheckLocationTokens.fonts.bodySemibold, fontSize: 13, marginLeft: 4, textAlign: 'right' },
  itemQuantity: { color: COLORS.muted, fontFamily: priceCheckLocationTokens.fonts.body, fontSize: 12, lineHeight: 17 },
  itemRow: { alignItems: 'center', borderBottomColor: '#E4EFE8', borderBottomWidth: 1, flexDirection: 'row', gap: 8, minHeight: 84, paddingHorizontal: 10, paddingVertical: 10 },
  lastItemRow: { borderBottomWidth: 0 },
  mutedItemText: { color: '#849391' },
  inputUnit: { color: COLORS.muted, fontFamily: priceCheckLocationTokens.fonts.bodySemibold, fontSize: 12 },
  unitDropdown: { alignItems: 'center', backgroundColor: 'transparent', flexDirection: 'row', gap: 2, minHeight: 31, minWidth: 56, paddingHorizontal: 0 },
  unitDropdownPlaceholder: { color: COLORS.muted },
  unitDropdownText: { color: COLORS.deepTeal, fontFamily: priceCheckLocationTokens.fonts.body, fontSize: 12 },
  unitOptionRow: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between', minHeight: 44, paddingHorizontal: 10 },
  unitOptionRowActive: { backgroundColor: COLORS.paleMint },
  unitOptionText: { color: COLORS.deepTeal, fontFamily: priceCheckLocationTokens.fonts.bodySemibold, fontSize: 12 },
  unitOptionTextActive: { color: COLORS.green },
  modifyButton: { alignItems: 'center', backgroundColor: COLORS.paleMint, borderRadius: 12, flexDirection: 'row', gap: 4, minHeight: 32, paddingHorizontal: 9 },
  modifyButtonText: { color: COLORS.deepTeal, fontFamily: priceCheckLocationTokens.fonts.bodySemibold, fontSize: 12 },
  pageSubtitle: { color: COLORS.muted, fontFamily: priceCheckLocationTokens.fonts.body, fontSize: 16, lineHeight: 22, marginTop: 6 },
  pageTitle: { color: COLORS.deepTeal, fontFamily: priceCheckLocationTokens.fonts.heading, fontSize: 29, lineHeight: 36 },
  pressed: { opacity: 0.8 },
  primaryButton: { alignItems: 'center', backgroundColor: COLORS.deepTeal, borderRadius: 17, flexDirection: 'row', gap: 10, justifyContent: 'center', marginTop: 22, minHeight: 56, paddingHorizontal: 16 },
  primaryButtonText: { color: COLORS.white, fontFamily: priceCheckLocationTokens.fonts.bodySemibold, fontSize: 16 },
  rawName: { color: COLORS.muted, fontFamily: priceCheckLocationTokens.fonts.body, fontSize: 11, lineHeight: 15 },
  replacementHint: { color: COLORS.muted, fontFamily: priceCheckLocationTokens.fonts.body, fontSize: 11, marginTop: 7 },
  replacementPicker: { backgroundColor: COLORS.white, borderColor: '#D6EAE0', borderRadius: 10, borderWidth: 1, marginTop: 4, padding: 8 },
  replacementResult: { alignItems: 'center', borderTopColor: '#E4EFE8', borderTopWidth: 1, flexDirection: 'row', justifyContent: 'space-between', marginTop: 6, minHeight: 35, paddingTop: 6 },
  replacementResultName: { color: COLORS.deepTeal, flex: 1, fontFamily: priceCheckLocationTokens.fonts.body, fontSize: 12 },
  replacementSearch: { backgroundColor: COLORS.paleMint, borderColor: '#DCEBE1', borderRadius: 8, borderWidth: 1, color: COLORS.deepTeal, fontFamily: priceCheckLocationTokens.fonts.body, fontSize: 12, minHeight: 36, paddingHorizontal: 9 },
  rowPressed: { backgroundColor: '#F6FBF8' },
  sectionHeader: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between', marginBottom: 10, marginTop: 24 },
  sectionTitle: { color: COLORS.deepTeal, fontFamily: priceCheckLocationTokens.fonts.cardTitle, fontSize: 18, lineHeight: 24 },
  step: { alignItems: 'center', backgroundColor: COLORS.paleMint, borderRadius: 16, flexDirection: 'row', gap: 5, minHeight: 32, paddingHorizontal: 9 },
  stepIndicator: { alignItems: 'center', flexDirection: 'row', justifyContent: 'center', marginTop: 4 },
  stepLabel: { color: COLORS.muted, fontFamily: priceCheckLocationTokens.fonts.bodySemibold, fontSize: 11 },
  stepLine: { backgroundColor: '#DCEBE1', height: 1, marginHorizontal: 6, width: 14 },
  stepText: { color: COLORS.muted, fontFamily: priceCheckLocationTokens.fonts.bodySemibold, fontSize: 12 },
  summaryCard: { alignItems: 'center', backgroundColor: COLORS.mint, borderRadius: 20, flexDirection: 'row', gap: 10, marginTop: 22, padding: 15 },
  summaryCopy: { flex: 1 },
  summaryIcon: { alignItems: 'center', backgroundColor: COLORS.white, borderRadius: 18, height: 38, justifyContent: 'center', width: 38 },
  summarySubtitle: { color: COLORS.muted, fontFamily: priceCheckLocationTokens.fonts.body, fontSize: 12, marginTop: 2 },
  summaryTitle: { color: COLORS.deepTeal, fontFamily: priceCheckLocationTokens.fonts.bodySemibold, fontSize: 14 },
  summaryTotal: { color: COLORS.deepTeal, fontFamily: priceCheckLocationTokens.fonts.cardTitle, fontSize: 16 },
  wrapper: { backgroundColor: COLORS.background, flex: 1 },
});
